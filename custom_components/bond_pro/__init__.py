"""The Bond Pro integration."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientTimeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import SLOW_UPDATE_WARNING

from .bond_async_pro import Bond, BPUPSubscriptions, RequestorUUID, start_bpup
from .const import BRIDGE_MAKE, DOMAIN
from .coordinator import BondFallbackCoordinator, BondTelemetryCoordinator
from .models import BondData
from .services import async_setup_services
from .utils import BondHub

PLATFORMS = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
_API_TIMEOUT = SLOW_UPDATE_WARNING - 1

_LOGGER = logging.getLogger(__name__)

type BondConfigEntry = ConfigEntry[BondData]


async def async_setup_entry(hass: HomeAssistant, entry: BondConfigEntry) -> bool:
    """Set up Bond Pro from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_ACCESS_TOKEN]
    config_entry_id = entry.entry_id

    bond = Bond(
        host=host,
        token=token,
        timeout=ClientTimeout(total=_API_TIMEOUT),
        session=async_get_clientsession(hass),
        requestor_uuid=RequestorUUID.HOME_ASSISTANT,
    )
    hub = BondHub(bond, host)
    try:
        await hub.setup()
    except ClientResponseError as ex:
        if ex.status == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed("Bond token is no longer valid") from ex
        raise ConfigEntryNotReady from ex
    except (ClientError, TimeoutError, OSError) as error:
        raise ConfigEntryNotReady from error

    bpup_subs = BPUPSubscriptions()
    stop_bpup = await start_bpup(host, bpup_subs)

    @callback
    def _async_stop_event(*_: Any) -> None:
        stop_bpup()

    entry.async_on_unload(_async_stop_event)
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _async_stop_event)
    )

    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=hub.bond_id)

    assert hub.bond_id is not None
    hub_name = hub.name or hub.bond_id
    device_registry = dr.async_get(hass)
    hub_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        identifiers={(DOMAIN, hub.bond_id)},
        manufacturer=BRIDGE_MAKE,
        name=hub_name,
        model=hub.target,
        sw_version=hub.fw_ver,
        hw_version=hub.mcu_ver,
        suggested_area=hub.location,
        configuration_url=f"http://{host}",
    )

    fallback = BondFallbackCoordinator(hass, entry, hub, bpup_subs)
    # hub.setup() already fetched every device's state; seed the coordinator
    # instead of refetching.
    fallback.async_set_updated_data(
        {device.device_id: device.state for device in hub.devices}
    )
    telemetry = BondTelemetryCoordinator(hass, entry, bond, hub)
    await telemetry.async_config_entry_first_refresh()

    entry.runtime_data = BondData(
        hub, hub_device_entry.id, bpup_subs, fallback, telemetry
    )

    async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BondConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: BondConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removal of a device that the hub no longer reports."""
    data = config_entry.runtime_data
    hub = data.hub
    valid_ids = {f"{hub.bond_id}_{device.device_id}" for device in hub.devices}
    valid_ids.add(hub.bond_id or hub.host)
    return not any(
        identifier[0] == DOMAIN and identifier[1] in valid_ids
        for identifier in device_entry.identifiers
    )
