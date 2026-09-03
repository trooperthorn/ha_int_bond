"""Support for Bond Pro hub services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

if TYPE_CHECKING:
    from . import BondConfigEntry

SERVICE_RF_SCAN = "rf_scan"
SERVICE_TRANSMIT_COMMAND = "transmit_command"
SERVICE_SET_FAN_SPEED_TRACKED_STATE = "set_fan_speed_tracked_state"
SERVICE_SET_LIGHT_POWER_TRACKED_STATE = "set_light_power_tracked_state"
SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE = "set_light_brightness_tracked_state"
SERVICE_SET_SWITCH_POWER_TRACKED_STATE = "set_switch_power_tracked_state"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DEVICE_ID = "device_id"
ATTR_COMMAND_ID = "command_id"
ATTR_POWER_STATE = "power_state"

RF_SCAN_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
)
TRANSMIT_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_COMMAND_ID): cv.string,
    }
)


def _async_get_entry(hass: HomeAssistant, call: ServiceCall) -> BondConfigEntry:
    """Resolve the target config entry for a hub service call."""
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id := call.data.get(ATTR_CONFIG_ENTRY_ID):
        for entry in loaded:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            f"Config entry {entry_id} not found or not loaded"
        )
    if len(loaded) == 1:
        return loaded[0]
    raise ServiceValidationError(
        "Multiple Bond hubs are configured; pass config_entry_id"
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Bond Pro hub-level services."""
    if hass.services.has_service(DOMAIN, SERVICE_RF_SCAN):
        return

    async def _async_rf_scan(call: ServiceCall) -> ServiceResponse:
        """Return an RF noise scan from the bridge."""
        entry = _async_get_entry(hass, call)
        bond = entry.runtime_data.hub.bond
        scan = await bond.signal_rssi()
        results: list[dict[str, Any]] = [
            {"freq_khz": freq, "rssi": rssi}
            for freq, rssi in scan.get("results", [])
        ]
        return {"results": results}

    async def _async_transmit_command(call: ServiceCall) -> None:
        """Transmit a stored device command's raw signal."""
        entry = _async_get_entry(hass, call)
        hub = entry.runtime_data.hub
        device_id: str = call.data[ATTR_DEVICE_ID]
        if not any(device.device_id == device_id for device in hub.devices):
            raise HomeAssistantError(
                f"Device {device_id} is not known to this Bond hub"
            )
        await hub.bond.transmit_command(device_id, call.data[ATTR_COMMAND_ID])

    hass.services.async_register(
        DOMAIN,
        SERVICE_RF_SCAN,
        _async_rf_scan,
        schema=RF_SCAN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSMIT_COMMAND,
        _async_transmit_command,
        schema=TRANSMIT_COMMAND_SCHEMA,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_FAN_SPEED_TRACKED_STATE,
        entity_domain=FAN_DOMAIN,
        schema={vol.Required("speed"): vol.All(vol.Coerce(int), vol.Range(0, 100))},
        func="async_set_speed_belief",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): vol.Coerce(bool)},
        func="async_set_power_belief",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            vol.Required(ATTR_BRIGHTNESS): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            )
        },
        func="async_set_brightness_belief",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SWITCH_POWER_TRACKED_STATE,
        entity_domain=SWITCH_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): vol.Coerce(bool)},
        func="async_set_power_belief",
    )
