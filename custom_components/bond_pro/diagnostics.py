"""Diagnostics support for Bond Pro."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BondConfigEntry

TO_REDACT = {"access_token", "addr", "ssid", "bssid", "mac", "ip", "gw", "dns"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BondConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    hub = data.hub

    wifi: dict[str, Any] = {}
    rf_scan: dict[str, Any] = {}
    try:
        wifi = await hub.bond.wifi_sta()
        rf_scan = await hub.bond.signal_rssi()
    except (ClientError, TimeoutError, OSError):
        pass

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "hub": {
            "version": hub.version_info,
            "bridge": hub.bridge_info,
            "wifi": async_redact_data(wifi, TO_REDACT),
            "rf_scan": rf_scan,
        },
        "bpup": {
            "alive": data.bpup_subs.alive,
        },
        "devices": [
            {
                "device_id": device.device_id,
                "props": async_redact_data(device.props, TO_REDACT),
                "attrs": device.attrs,
                "state": device.state,
                "supported_actions": sorted(device.supported_actions),
            }
            for device in hub.devices
        ],
    }
