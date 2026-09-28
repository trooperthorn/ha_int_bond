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

from .bond_async_pro import Action
from .const import DOMAIN

if TYPE_CHECKING:
    from . import BondConfigEntry

SERVICE_RF_SCAN = "rf_scan"
SERVICE_TRANSMIT_COMMAND = "transmit_command"
SERVICE_SET_FAN_SPEED_TRACKED_STATE = "set_fan_speed_tracked_state"
SERVICE_SET_LIGHT_POWER_TRACKED_STATE = "set_light_power_tracked_state"
SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE = "set_light_brightness_tracked_state"
SERVICE_SET_SWITCH_POWER_TRACKED_STATE = "set_switch_power_tracked_state"
SERVICE_RELOAD_DEVICE = "reload_device"
SERVICE_LIST_SKEDS = "list_skeds"
SERVICE_CREATE_SKED = "create_sked"
SERVICE_UPDATE_SKED = "update_sked"
SERVICE_DELETE_SKED = "delete_sked"
SERVICE_CHANNEL_ACTION = "channel_action"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DEVICE_ID = "device_id"
ATTR_COMMAND_ID = "command_id"
ATTR_POWER_STATE = "power_state"
ATTR_TARGET_TYPE = "target_type"
ATTR_TARGET_ID = "target_id"
ATTR_SKED_ID = "sked_id"
ATTR_CHANNEL_ID = "channel_id"
ATTR_ACTION = "action"
ATTR_ARGUMENT = "argument"

# Sked owners and their URL collections (/v2/{collection}/{id}/skeds).
SKED_TARGETS = {
    "device": "devices",
    "group": "groups",
    "scene": "scenes",
    "channel": "channels",
}
SKED_MARKS = ["midnight", "sunrise", "sunset", "dawn", "dusk"]
SKED_FIELDS = {
    vol.Optional("enabled"): cv.boolean,
    vol.Optional(ATTR_ACTION): cv.string,
    vol.Optional(ATTR_ARGUMENT): object,
    vol.Optional("seconds"): vol.Coerce(int),
    # Sunday first; all false means run once, then the sked disables itself.
    vol.Optional("days_of_week"): vol.All(
        cv.ensure_list, [cv.boolean], vol.Length(min=7, max=7)
    ),
    vol.Optional("mark"): vol.In(SKED_MARKS),
}
SKED_TARGET_FIELDS = {
    vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    vol.Required(ATTR_TARGET_TYPE): vol.In(list(SKED_TARGETS)),
    vol.Required(ATTR_TARGET_ID): cv.string,
}

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

RELOAD_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.string,
    }
)
LIST_SKEDS_SCHEMA = vol.Schema(SKED_TARGET_FIELDS)
# seconds, days_of_week and mark are required when creating a sked.
CREATE_SKED_SCHEMA = vol.Schema(
    {
        **SKED_TARGET_FIELDS,
        **{
            (
                vol.Required(key.schema)
                if key.schema in ("seconds", "days_of_week", "mark")
                else key
            ): validator
            for key, validator in SKED_FIELDS.items()
        },
    }
)
UPDATE_SKED_SCHEMA = vol.Schema(
    {**SKED_TARGET_FIELDS, vol.Required(ATTR_SKED_ID): cv.string, **SKED_FIELDS}
)
DELETE_SKED_SCHEMA = vol.Schema(
    {**SKED_TARGET_FIELDS, vol.Required(ATTR_SKED_ID): cv.string}
)
CHANNEL_ACTION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_CHANNEL_ID): cv.string,
        vol.Required(ATTR_ACTION): cv.string,
        vol.Optional(ATTR_ARGUMENT): object,
    }
)


def _sked_body(data: dict[str, Any]) -> dict[str, Any]:
    """Return only the sked fields of a service call."""
    return {
        key.schema: data[key.schema]
        for key in SKED_FIELDS
        if key.schema in data
    }


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

    async def _async_reload_device(call: ServiceCall) -> None:
        """Rebuild a templated device's default command table."""
        entry = _async_get_entry(hass, call)
        hub = entry.runtime_data.hub
        device_id: str = call.data[ATTR_DEVICE_ID]
        device = next((d for d in hub.devices if d.device_id == device_id), None)
        if device is None:
            raise HomeAssistantError(
                f"Device {device_id} is not known to this Bond hub"
            )
        if not device.template:
            raise ServiceValidationError(
                f"Device {device_id} has no template and cannot be reloaded"
            )
        await hub.bond.reload_device(device_id)

    async def _async_list_skeds(call: ServiceCall) -> ServiceResponse:
        """Return every sked of a device, group, scene or channel."""
        bond = _async_get_entry(hass, call).runtime_data.hub.bond
        skeds = await bond.skeds(
            SKED_TARGETS[call.data[ATTR_TARGET_TYPE]], call.data[ATTR_TARGET_ID]
        )
        return {"skeds": skeds}

    async def _async_create_sked(call: ServiceCall) -> ServiceResponse:
        """Create a sked and return its ID."""
        target_type = call.data[ATTR_TARGET_TYPE]
        body = _sked_body(call.data)
        if target_type == "scene":
            if ATTR_ACTION in body:
                raise ServiceValidationError("Scene skeds must not set an action")
        elif ATTR_ACTION not in body:
            raise ServiceValidationError(f"A {target_type} sked needs an action")
        bond = _async_get_entry(hass, call).runtime_data.hub.bond
        created = await bond.create_sked(
            SKED_TARGETS[target_type], call.data[ATTR_TARGET_ID], body
        )
        return {"sked_id": created.get("_id")}

    async def _async_update_sked(call: ServiceCall) -> None:
        """Change fields of a sked."""
        bond = _async_get_entry(hass, call).runtime_data.hub.bond
        await bond.update_sked(
            SKED_TARGETS[call.data[ATTR_TARGET_TYPE]],
            call.data[ATTR_TARGET_ID],
            call.data[ATTR_SKED_ID],
            _sked_body(call.data),
        )

    async def _async_delete_sked(call: ServiceCall) -> None:
        """Delete a sked."""
        bond = _async_get_entry(hass, call).runtime_data.hub.bond
        await bond.delete_sked(
            SKED_TARGETS[call.data[ATTR_TARGET_TYPE]],
            call.data[ATTR_TARGET_ID],
            call.data[ATTR_SKED_ID],
        )

    async def _async_channel_action(call: ServiceCall) -> None:
        """Run an action on a Mate Pro / Sidekick Blue channel."""
        bond = _async_get_entry(hass, call).runtime_data.hub.bond
        await bond.channel_action(
            call.data[ATTR_CHANNEL_ID],
            Action(call.data[ATTR_ACTION], call.data.get(ATTR_ARGUMENT)),
        )

    for name, handler, schema, response in (
        (SERVICE_RELOAD_DEVICE, _async_reload_device, RELOAD_DEVICE_SCHEMA, None),
        (SERVICE_LIST_SKEDS, _async_list_skeds, LIST_SKEDS_SCHEMA, SupportsResponse.ONLY),
        (SERVICE_CREATE_SKED, _async_create_sked, CREATE_SKED_SCHEMA, SupportsResponse.OPTIONAL),
        (SERVICE_UPDATE_SKED, _async_update_sked, UPDATE_SKED_SCHEMA, None),
        (SERVICE_DELETE_SKED, _async_delete_sked, DELETE_SKED_SCHEMA, None),
        (SERVICE_CHANNEL_ACTION, _async_channel_action, CHANNEL_ACTION_SCHEMA, None),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=response or SupportsResponse.NONE,
        )

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
