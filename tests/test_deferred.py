"""Tests for the Local API features that used to be deferred.

Groups, scenes, schedules, reboot/identify, power, BPUP broadcast, shade
tilt/rails/layers, Raise/Lower-only shades and heat.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.bond_pro.bond_async_pro import Action
from custom_components.bond_pro.const import DOMAIN

from .common import (
    BOND_ID,
    DEVICES,
    FAN_ID,
    make_client_response_error,
    setup_bond,
)

BOND = "custom_components.bond_pro.bond_async_pro.Bond"

SHADE_ID = "a1b2c3d4e5f60708"
SHADE = {
    "attrs": {
        "name": "Kitchen Shade",
        "type": "MS",
        "location": "Kitchen",
        "actions": [
            "Raise",
            "Lower",
            "Hold",
            "SetPosition",
            "SetTiltPosition",
            "ToggleTilt",
            "SetUpperRailPosition",
            "SetLowerRailPosition",
            "RaiseUpperRail",
            "LowerUpperRail",
            "RaiseLowerRail",
            "LowerLowerRail",
            "SetSheerPosition",
        ],
    },
    "props": {"trust_state": True, "min_tilt": -90, "max_tilt": 90},
    "state": {
        "open": 1,
        "position": 0,
        "tilt_position": 0,
        "upper_rail_position": 0,
        "lower_rail_position": 40,
        "sheer_position": 100,
    },
}
HEATER_ID = "0f0e0d0c0b0a0908"
HEATER = {
    "attrs": {
        "name": "Patio Heater",
        "type": "GX",
        "actions": [
            "TurnOn",
            "TurnOff",
            "SetHeat",
            "IncreaseHeat",
            "DecreaseHeat",
            "HeatPresetNext",
            "HeatPresetPrev",
        ],
    },
    "props": {"trust_state": True},
    "state": {"power": 1, "heat": 60},
}
GROUP_ID = "3b20f30011223344"
GROUP = {
    "attrs": {
        "name": "Kitchen Shades",
        "devices": [SHADE_ID],
        "types": ["MS"],
        "locations": ["Kitchen"],
        "actions": ["Open", "Close", "Hold"],
    },
    "props": {},
    "state": {"open": None},
}
SCENE_ID = "5c0e0001"
SCENE = {
    "name": "Privacy",
    "actors": [{"group": GROUP_ID, "action": "Close"}],
    "types": ["MS"],
}

ALL_DEVICES = {**DEVICES, SHADE_ID: SHADE, HEATER_ID: HEATER}


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None, unique_id
    return entity_id


async def _setup(hass: HomeAssistant, **kwargs: Any) -> None:
    await setup_bond(
        hass,
        devices=ALL_DEVICES,
        groups={GROUP_ID: GROUP},
        scenes={SCENE_ID: SCENE},
        **kwargs,
    )


async def _call(hass: HomeAssistant, domain: str, service: str, data: dict) -> None:
    await hass.services.async_call(domain, service, data, blocking=True)


async def test_group_cover_routes_to_group(hass: HomeAssistant) -> None:
    """A single-type group becomes a cover whose actions hit /v2/groups."""
    await _setup(hass)
    cover = _entity_id(hass, "cover", f"{BOND_ID}_{GROUP_ID}")
    # Members disagree: open is null, so the state is unknown.
    assert hass.states.get(cover).state == "unknown"

    with (
        patch(f"{BOND}.group_action", AsyncMock()) as group_action,
        patch(f"{BOND}.action", AsyncMock()) as device_action,
    ):
        await _call(hass, "cover", "close_cover", {"entity_id": cover})
    group_action.assert_awaited_once_with(GROUP_ID, Action(Action.CLOSE))
    device_action.assert_not_awaited()


async def test_scene_runs(hass: HomeAssistant) -> None:
    """Scene entities run the bridge scene."""
    await _setup(hass)
    scene = _entity_id(hass, "scene", f"{BOND_ID}_scene_{SCENE_ID}")
    assert hass.states.get(scene).attributes["actors"] == SCENE["actors"]

    with patch(f"{BOND}.run_scene", AsyncMock()) as run_scene:
        await _call(hass, "scene", "turn_on", {"entity_id": scene})
    run_scene.assert_awaited_once_with(SCENE_ID)


async def test_raise_lower_only_shade(hass: HomeAssistant) -> None:
    """Shades without Open/Close open with Raise and close with Lower."""
    await _setup(hass)
    cover = _entity_id(hass, "cover", f"{BOND_ID}_{SHADE_ID}")

    with patch(f"{BOND}.action", AsyncMock()) as action:
        await _call(hass, "cover", "open_cover", {"entity_id": cover})
        await _call(hass, "cover", "close_cover", {"entity_id": cover})
    assert [c.args[1] for c in action.await_args_list] == [
        Action(Action.RAISE),
        Action(Action.LOWER),
    ]


async def test_tilt_position_scaling(hass: HomeAssistant) -> None:
    """Tilt maps HA 0-100 onto min_tilt..max_tilt degrees."""
    await _setup(hass)
    cover = _entity_id(hass, "cover", f"{BOND_ID}_{SHADE_ID}")
    # 0 degrees in a -90..90 range is the midpoint.
    assert hass.states.get(cover).attributes["current_tilt_position"] == 50

    with patch(f"{BOND}.action", AsyncMock()) as action:
        await _call(
            hass,
            "cover",
            "set_cover_tilt_position",
            {"entity_id": cover, "tilt_position": 100},
        )
    action.assert_awaited_once_with(SHADE_ID, Action(Action.SET_TILT_POSITION, 90))
    assert _entity_id(hass, "button", f"{BOND_ID}_{SHADE_ID}_toggletilt")


async def test_rail_and_layer_covers(hass: HomeAssistant) -> None:
    """TDBU rails and the sheer layer get their own covers."""
    await _setup(hass)
    lower = _entity_id(hass, "cover", f"{BOND_ID}_{SHADE_ID}_lower_rail")
    sheer = _entity_id(hass, "cover", f"{BOND_ID}_{SHADE_ID}_sheer")
    assert hass.states.get(lower).attributes["current_position"] == 60
    assert hass.states.get(sheer).state == "closed"
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(
            "cover", DOMAIN, f"{BOND_ID}_{SHADE_ID}_blackout"
        )
        is None
    )

    with patch(f"{BOND}.action", AsyncMock()) as action:
        await _call(hass, "cover", "open_cover", {"entity_id": lower})
        await _call(
            hass, "cover", "set_cover_position", {"entity_id": sheer, "position": 25}
        )
    assert [c.args[1] for c in action.await_args_list] == [
        Action(Action.RAISE_LOWER_RAIL),
        Action(Action.SET_SHEER_POSITION, 75),
    ]


async def test_heat(hass: HomeAssistant) -> None:
    """Heat number sets SetHeat, 0 turns off; step buttons exist."""
    await _setup(hass)
    heat = _entity_id(hass, "number", f"{BOND_ID}_{HEATER_ID}_heat")
    assert hass.states.get(heat).state == "60"
    assert _entity_id(hass, "button", f"{BOND_ID}_{HEATER_ID}_heatpresetnext")

    with patch(f"{BOND}.action", AsyncMock()) as action:
        await _call(hass, "number", "set_value", {"entity_id": heat, "value": 35})
        await _call(hass, "number", "set_value", {"entity_id": heat, "value": 0})
    assert [c.args[1] for c in action.await_args_list] == [
        Action(Action.SET_HEAT, 35),
        Action.turn_off(),
    ]


async def test_reboot_button(hass: HomeAssistant) -> None:
    """The restart button reboots the bridge."""
    await _setup(hass)
    button = _entity_id(hass, "button", f"{BOND_ID}_reboot")
    with patch(f"{BOND}.reboot", AsyncMock()) as reboot:
        await _call(hass, "button", "press", {"entity_id": button})
    reboot.assert_awaited_once_with()


async def test_optional_bridge_endpoints_absent(hass: HomeAssistant) -> None:
    """404 on indicate/power means no identify button or power sensors."""
    await _setup(hass)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("button", DOMAIN, f"{BOND_ID}_identify") is None
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{BOND_ID}_power_dc_mv")
        is None
    )


async def test_identify_and_power_present(hass: HomeAssistant) -> None:
    """Supported indicate/power endpoints create identify and power entities."""
    await _setup(
        hass,
        overrides={
            "indicate": AsyncMock(return_value={"identify": 0, "commit": 0}),
            "power": AsyncMock(
                return_value={
                    "poe_active": False,
                    "dc_mV": 23812,
                    "dc_mA": None,
                    "pcb_mC": 29500,
                }
            ),
        },
    )
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{BOND_ID}_power_dc_ma") is None
    voltage = _entity_id(hass, "sensor", f"{BOND_ID}_power_dc_mv")
    assert hass.states.get(voltage).state == "23812"
    board = _entity_id(hass, "sensor", f"{BOND_ID}_power_pcb_mc")
    assert float(hass.states.get(board).state) == pytest.approx(29.5)

    identify = _entity_id(hass, "button", f"{BOND_ID}_identify")
    with patch(f"{BOND}.set_indicate", AsyncMock()) as set_indicate:
        await _call(hass, "button", "press", {"entity_id": identify})
    set_indicate.assert_awaited_once_with(10)


async def test_bpup_broadcast_switch_disabled_by_default(hass: HomeAssistant) -> None:
    """The broadcast switch exists but starts disabled."""
    await _setup(hass)
    registry = er.async_get(hass)
    entity_id = _entity_id(hass, "switch", f"{BOND_ID}_bpup_broadcast")
    assert registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_sked_services(hass: HomeAssistant) -> None:
    """Sked services validate input and call the right collection."""
    await _setup(hass)
    sked = {
        "action": "SetPosition",
        "argument": 50,
        "seconds": -600,
        "days_of_week": [False, True, True, True, True, True, False],
        "mark": "sunset",
    }
    with patch(f"{BOND}.create_sked", AsyncMock(return_value={"_id": "01234567"})) as create:
        response = await hass.services.async_call(
            DOMAIN,
            "create_sked",
            {"target_type": "group", "target_id": GROUP_ID, **sked},
            blocking=True,
            return_response=True,
        )
    create.assert_awaited_once_with("groups", GROUP_ID, sked)
    assert response == {"sked_id": "01234567"}

    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            DOMAIN,
            "create_sked",
            {"target_type": "scene", "target_id": SCENE_ID, **sked},
        )

    with patch(f"{BOND}.skeds", AsyncMock(return_value={"01234567": sked})) as skeds:
        response = await hass.services.async_call(
            DOMAIN,
            "list_skeds",
            {"target_type": "device", "target_id": FAN_ID},
            blocking=True,
            return_response=True,
        )
    skeds.assert_awaited_once_with("devices", FAN_ID)
    assert response == {"skeds": {"01234567": sked}}

    with patch(f"{BOND}.update_sked", AsyncMock()) as update:
        await _call(
            hass,
            DOMAIN,
            "update_sked",
            {
                "target_type": "device",
                "target_id": FAN_ID,
                "sked_id": "01234567",
                "enabled": False,
            },
        )
    update.assert_awaited_once_with("devices", FAN_ID, "01234567", {"enabled": False})

    with patch(f"{BOND}.delete_sked", AsyncMock()) as delete:
        await _call(
            hass,
            DOMAIN,
            "delete_sked",
            {"target_type": "device", "target_id": FAN_ID, "sked_id": "01234567"},
        )
    delete.assert_awaited_once_with("devices", FAN_ID, "01234567")


async def test_reload_device_requires_template(hass: HomeAssistant) -> None:
    """reload_device refuses devices without a template."""
    await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await _call(hass, DOMAIN, "reload_device", {"device_id": HEATER_ID})


async def test_channel_action(hass: HomeAssistant) -> None:
    """channel_action PUTs the action to the channel."""
    await _setup(hass)
    with patch(f"{BOND}.channel_action", AsyncMock()) as channel_action:
        await _call(
            hass,
            DOMAIN,
            "channel_action",
            {"channel_id": "3", "action": "Open"},
        )
    channel_action.assert_awaited_once_with("3", Action("Open"))


async def test_setup_without_groups_or_scenes(hass: HomeAssistant) -> None:
    """Bridges answering 404 for groups and scenes still set up."""
    await setup_bond(
        hass,
        overrides={
            "groups": AsyncMock(side_effect=make_client_response_error(404)),
            "scenes": AsyncMock(side_effect=make_client_response_error(404)),
        },
    )
    assert hass.states.async_entity_ids("scene") == []

