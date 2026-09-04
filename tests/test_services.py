"""Tests for Bond Pro hub services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.bond_pro.const import DOMAIN

from .common import FAN_ID, setup_bond

RF_SCAN = {"format": ["freq", "rssi"], "results": [[314960, 68], [433850, 48]]}


async def test_rf_scan_service(hass: HomeAssistant) -> None:
    """rf_scan returns the bridge's noise scan as response data."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.signal_rssi", AsyncMock(return_value=RF_SCAN)):
        response = await hass.services.async_call(
            DOMAIN,
            "rf_scan",
            {},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "results": [
            {"freq_khz": 314960, "rssi": 68},
            {"freq_khz": 433850, "rssi": 48},
        ]
    }


async def test_transmit_command_service(hass: HomeAssistant) -> None:
    """transmit_command validates the device and transmits."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.transmit_command", AsyncMock()) as transmit:
        await hass.services.async_call(
            DOMAIN,
            "transmit_command",
            {"device_id": FAN_ID, "command_id": "cmd123"},
            blocking=True,
        )
    transmit.assert_called_once_with(FAN_ID, "cmd123")


async def test_transmit_command_unknown_device(hass: HomeAssistant) -> None:
    """transmit_command refuses devices the hub does not know."""
    await setup_bond(hass)

    with (
        patch("custom_components.bond_pro.bond_async_pro.Bond.transmit_command", AsyncMock()) as transmit,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "transmit_command",
            {"device_id": "nope", "command_id": "cmd123"},
            blocking=True,
        )
    transmit.assert_not_called()


async def test_fan_speed_tracked_state(hass: HomeAssistant) -> None:
    """The tracked-state entity service patches state belief."""
    await setup_bond(hass)

    with patch("custom_components.bond_pro.bond_async_pro.Bond.action", AsyncMock()) as action:
        await hass.services.async_call(
            DOMAIN,
            "set_fan_speed_tracked_state",
            {"entity_id": "fan.master_bedroom_master_fan", "speed": 50},
            blocking=True,
        )
    # Two calls: power belief then speed belief.
    assert action.call_count == 2
