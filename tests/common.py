"""Common helpers for Bond Pro tests.

Fixture payloads mirror a real Bond Bridge BD-1000 (fw v4.32.7) so the tests
exercise the same shapes the integration sees in production.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant

from custom_components.bond_pro.const import DOMAIN

HOST = "192.168.1.9"
TOKEN = "test-token"
BOND_ID = "ZZCJ11057"

VERSION = {
    "target": "zermatt-2",
    "fw_ver": "v4.32.7",
    "make": "Olibra",
    "model": "BD-1000",
    "bondid": BOND_ID,
    "uptime_s": 448638,
    "api": 2,
}

BRIDGE = {"name": "Master BRIDGE", "location": "Lab", "bluelight": 30}

WIFI_STA = {"ssid": "d2lmaW90", "rssi": -72, "ip": "192.168.1.9", "gw": "192.168.1.1"}

FAN_ID = "f3b20e39bfe4459a"
FAN_DEVICE = {
    "name": "Master Fan",
    "type": "CF",
    "location": "Master Bedroom",
    "actions": [
        "DecreaseSpeed",
        "IncreaseSpeed",
        "SetSpeed",
        "Stop",
        "TogglePower",
        "TurnOff",
        "TurnOn",
    ],
}
FAN_PROPS = {"trust_state": False}
FAN_STATE = {"power": 0, "speed": 0}

FAN_LIGHT_ID = "65ae037b443e1769"
FAN_LIGHT_DEVICE = {
    "name": "Front Bedroom",
    "type": "CF",
    "location": "Front Bedroom",
    "template": "L2",
    "actions": [
        "DecreaseSpeed",
        "IncreaseSpeed",
        "SetSpeed",
        "StartDimmer",
        "Stop",
        "ToggleLight",
        "TogglePower",
        "TurnLightOff",
        "TurnLightOn",
        "TurnOff",
        "TurnOn",
    ],
}
FAN_LIGHT_PROPS = {
    "addr": "1110100100010110",
    "freq": 314960,
    "zero_gap": 28,
    "bps": 2251,
    "max_speed": 3,
    "trust_state": False,
}
FAN_LIGHT_STATE = {"power": 0, "speed": 3, "light": 0}

SWITCH_ID = "64f61c2d20060e2f"
SWITCH_DEVICE = {
    "name": "Christmas Tree",
    "type": "GX",
    "location": "Dining Room",
    "actions": ["Stop", "TogglePower", "TurnOff", "TurnOn"],
}
SWITCH_PROPS = {"trust_state": False}
SWITCH_STATE = {"power": 0}

FIREPLACE_ID = "f06d5925aff2010c"
FIREPLACE_DEVICE = {
    "name": "Fireplace",
    "type": "FP",
    "location": "Lab",
    "actions": ["TurnOn", "TurnOff", "SetFlame", "Stop"],
}
FIREPLACE_PROPS = {"trust_state": False}
FIREPLACE_STATE = {"power": 0, "flame": 0}

DEVICES: dict[str, dict[str, Any]] = {
    FAN_ID: {"attrs": FAN_DEVICE, "props": FAN_PROPS, "state": FAN_STATE},
    FAN_LIGHT_ID: {
        "attrs": FAN_LIGHT_DEVICE,
        "props": FAN_LIGHT_PROPS,
        "state": FAN_LIGHT_STATE,
    },
    SWITCH_ID: {"attrs": SWITCH_DEVICE, "props": SWITCH_PROPS, "state": SWITCH_STATE},
    FIREPLACE_ID: {
        "attrs": FIREPLACE_DEVICE,
        "props": FIREPLACE_PROPS,
        "state": FIREPLACE_STATE,
    },
}


def make_client_response_error(status: int) -> ClientResponseError:
    """Build a ClientResponseError with the given status."""
    return ClientResponseError(
        request_info=MagicMock(), history=(), status=status, message="error"
    )


@contextmanager
def patch_bond_api(
    devices: dict[str, dict[str, Any]] | None = None,
    version: dict[str, Any] | None = None,
    version_side_effect: Exception | None = None,
):
    """Patch every bond_async.Bond method the integration calls."""
    if devices is None:
        devices = DEVICES
    if version is None:
        version = VERSION

    def _device(self, device_id):  # noqa: ANN001
        return devices[device_id]["attrs"]

    def _props(self, device_id):  # noqa: ANN001
        return devices[device_id]["props"]

    def _state(self, device_id):  # noqa: ANN001
        return devices[device_id]["state"]

    version_mock = AsyncMock(return_value=version)
    if version_side_effect is not None:
        version_mock = AsyncMock(side_effect=version_side_effect)

    with (
        # HA's shared session creates an aiodns resolver, which cannot even
        # be constructed on a Windows proactor loop; the session is never
        # used because every Bond method is mocked below.
        patch(
            "custom_components.bond_pro.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.bond_pro.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("bond_async.Bond.version", version_mock),
        patch("bond_async.Bond.devices", AsyncMock(return_value=list(devices))),
        patch("bond_async.Bond.device", autospec=True, side_effect=_device),
        patch(
            "bond_async.Bond.device_properties", autospec=True, side_effect=_props
        ),
        patch("bond_async.Bond.device_state", autospec=True, side_effect=_state),
        patch("bond_async.Bond.bridge", AsyncMock(return_value=dict(BRIDGE))),
        patch("bond_async.Bond.wifi_sta", AsyncMock(return_value=dict(WIFI_STA))),
        patch("bond_async.Bond.action", AsyncMock()) as action_mock,
    ):
        yield action_mock


@contextmanager
def patch_start_bpup():
    """Patch BPUP startup so no UDP socket is created."""
    with patch(
        "custom_components.bond_pro.start_bpup",
        AsyncMock(return_value=MagicMock()),
    ) as start_bpup_mock:
        yield start_bpup_mock


def make_entry(unique_id: str | None = BOND_ID) -> MockConfigEntry:
    """Create a config entry for the test bridge."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title="Master BRIDGE",
        data={CONF_HOST: HOST, CONF_ACCESS_TOKEN: TOKEN},
    )


async def setup_bond(
    hass: HomeAssistant,
    devices: dict[str, dict[str, Any]] | None = None,
) -> MockConfigEntry:
    """Set up the integration with a mocked bridge; returns the entry."""
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch_bond_api(devices=devices), patch_start_bpup():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry
