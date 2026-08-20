"""Tests for Bond Pro entity platforms (fan, light, switch, number, sensor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from custom_components.bond_pro.bond_async_pro import Action

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.bond_pro.const import DOMAIN

from .common import (
    BOND_ID,
    FAN_ID,
    FAN_LIGHT_ID,
    FIREPLACE_ID,
    patch_bond_api,
    setup_bond,
)

FAN_ENTITY = "fan.master_fan"
FAN_LIGHT_ENTITY = "light.front_bedroom_light"
SWITCH_ENTITY = "switch.christmas_tree"
FLAME_ENTITY = "number.fireplace_flame"
BLUE_LIGHT_ENTITY = "light.master_bridge_blue_light"
RSSI_ENTITY = "sensor.master_bridge_wi_fi_signal"


async def test_entities_created(hass: HomeAssistant) -> None:
    """Every expected entity is created with the right unique_id."""
    await setup_bond(hass)
    registry = er.async_get(hass)

    fan = registry.async_get(FAN_ENTITY)
    assert fan is not None
    assert fan.unique_id == f"{BOND_ID}_{FAN_ID}"

    light = registry.async_get(FAN_LIGHT_ENTITY)
    assert light is not None
    assert light.unique_id == f"{BOND_ID}_{FAN_LIGHT_ID}_light"

    assert registry.async_get(SWITCH_ENTITY) is not None

    flame = registry.async_get(FLAME_ENTITY)
    assert flame is not None
    assert flame.unique_id == f"{BOND_ID}_{FIREPLACE_ID}_flame"

    assert registry.async_get(BLUE_LIGHT_ENTITY) is not None
    assert registry.async_get(RSSI_ENTITY) is not None


async def test_fan_state_and_speed(hass: HomeAssistant) -> None:
    """Fan reflects bridge state and converts speed to percentage."""
    await setup_bond(hass)

    state = hass.states.get(FAN_ENTITY)
    assert state is not None
    assert state.state == STATE_OFF
    # Front Bedroom fan is off but its stored speed is 3 of max 3.
    light_fan = hass.states.get("fan.front_bedroom")
    assert light_fan.attributes["percentage"] == 0


async def test_fan_actions(hass: HomeAssistant) -> None:
    """Fan services translate into Bond actions."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: FAN_ENTITY},
            blocking=True,
        )
    action.assert_called_once()
    assert action.call_args[0][0] == FAN_ID
    assert action.call_args[0][1] == Action.turn_on()

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: "fan.front_bedroom", ATTR_PERCENTAGE: 100},
            blocking=True,
        )
    assert action.call_args[0][1] == Action.set_speed(3)


async def test_bpup_push_updates_state(hass: HomeAssistant) -> None:
    """A BPUP frame updates entity state without any polling."""
    entry = await setup_bond(hass)
    bpup_subs = entry.runtime_data.bpup_subs

    assert hass.states.get(FAN_ENTITY).state == STATE_OFF

    bpup_subs.notify(
        {
            "s": 200,
            "t": f"devices/{FAN_ID}/state",
            "b": {"power": 1, "speed": 2},
        }
    )
    await hass.async_block_till_done()

    state = hass.states.get(FAN_ENTITY)
    assert state.state == "on"
    assert state.attributes["percentage"] == 66


async def test_light_actions(hass: HomeAssistant) -> None:
    """Light on/off translate into Bond light actions."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: FAN_LIGHT_ENTITY},
            blocking=True,
        )
    assert action.call_args[0][1] == Action.turn_light_on()

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: FAN_LIGHT_ENTITY},
            blocking=True,
        )
    assert action.call_args[0][1] == Action.turn_light_off()


async def test_blue_light(hass: HomeAssistant) -> None:
    """The bridge ring light reflects bluelight brightness and patches it."""
    await setup_bond(hass)

    state = hass.states.get(BLUE_LIGHT_ENTITY)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 30

    with (
        patch_bond_api(),
        patch(
            "custom_components.bond_pro.bond_async_pro.Bond.set_bluelight_brightness", AsyncMock()
        ) as set_bluelight,
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: BLUE_LIGHT_ENTITY},
            blocking=True,
        )
        await hass.async_block_till_done()
    set_bluelight.assert_called_once_with(0)


async def test_wifi_rssi_sensor(hass: HomeAssistant) -> None:
    """The bridge Wi-Fi signal sensor reports dBm from sys/wifi/sta."""
    await setup_bond(hass)

    state = hass.states.get(RSSI_ENTITY)
    assert state is not None
    assert state.state == "-72"
    assert state.attributes["unit_of_measurement"] == "dBm"


async def test_rf_frequency_sensor_disabled_by_default(hass: HomeAssistant) -> None:
    """Per-device RF frequency sensors exist but start disabled."""
    await setup_bond(hass)
    registry = er.async_get(hass)

    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BOND_ID}_{FAN_LIGHT_ID}_rf_frequency"
    )
    assert entity is not None
    entry = registry.async_get(entity)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_flame_number(hass: HomeAssistant) -> None:
    """The flame number sets flame via SetFlame and off at zero."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: FLAME_ENTITY, "value": 55},
            blocking=True,
        )
    assert action.call_args[0][0] == FIREPLACE_ID
    assert action.call_args[0][1] == Action.set_flame(55)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: FLAME_ENTITY, "value": 0},
            blocking=True,
        )
    assert action.call_args[0][1] == Action.turn_off()
