"""Tests for bridge fault reporting and the Pair feature buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.bond_pro.bond_async_pro import Action
from custom_components.bond_pro.const import DOMAIN

from .common import (
    BOND_ID,
    SWITCH_ID,
    make_client_response_error,
    make_entry,
    patch_bond_api,
    patch_start_bpup,
    setup_bond,
)

FAULTS_ENTITY = "binary_sensor.lab_master_bridge_faults"
CLEAR_FAULTS_ENTITY = "button.lab_master_bridge_clear_faults"


async def _setup(hass: HomeAssistant, **api_kwargs) -> None:
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch_bond_api(**api_kwargs), patch_start_bpup():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_faults_sensor_clear(hass: HomeAssistant) -> None:
    """No listed fault means the problem sensor is off."""
    await setup_bond(hass)

    state = hass.states.get(FAULTS_ENTITY)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["faults"] == []
    assert state.attributes["raise_count"] == 0


async def test_faults_sensor_raised(hass: HomeAssistant) -> None:
    """A listed fault turns the sensor on; unknown names pass through."""
    await _setup(
        hass,
        faults={
            "controller": {
                "faults": [
                    {"fault": "overtemp", "unix_time": 1758729655},
                    {"fault": "future_fault", "unix_time": 1758729656},
                ],
                "raise_count": 3,
            }
        },
    )

    state = hass.states.get(FAULTS_ENTITY)
    assert state.state == STATE_ON
    assert state.attributes["faults"] == ["future_fault", "overtemp"]
    assert state.attributes["raise_count"] == 3


async def test_faults_unsupported(hass: HomeAssistant) -> None:
    """Bridges answering 404 get no fault entities and setup still succeeds."""
    await _setup(hass, faults_side_effect=make_client_response_error(404))

    assert hass.states.get(FAULTS_ENTITY) is None
    assert hass.states.get(CLEAR_FAULTS_ENTITY) is None


async def test_clear_faults_button(hass: HomeAssistant) -> None:
    """Pressing Clear faults PATCHes the clear flag."""
    await setup_bond(hass)

    with (
        patch_bond_api(),
        patch(
            "custom_components.bond_pro.bond_async_pro.Bond.clear_faults",
            AsyncMock(),
        ) as clear,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: CLEAR_FAULTS_ENTITY},
            blocking=True,
        )
    clear.assert_awaited_once_with()


async def test_pairing_buttons(hass: HomeAssistant) -> None:
    """Pair/Unpair buttons exist only for exposed actions, disabled by default."""
    await setup_bond(hass)
    registry = er.async_get(hass)

    for action in (Action.PAIR, Action.UNPAIR):
        entity_id = registry.async_get_entity_id(
            "button", DOMAIN, f"{BOND_ID}_{SWITCH_ID}_{action.lower()}"
        )
        assert entity_id is not None
        entry = registry.async_get(entity_id)
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert entry.entity_category == "config"

    assert (
        registry.async_get_entity_id(
            "button", DOMAIN, f"{BOND_ID}_{SWITCH_ID}_{Action.UNPAIR_SELF.lower()}"
        )
        is None
    )
