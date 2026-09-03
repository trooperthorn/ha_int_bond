"""Support for Bond Pro diagnostic sensors (new vs upstream)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfFrequency,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BondConfigEntry
from .entity import BondHubEntity, bond_device_info
from .models import BondData
from .utils import BondDevice

PARALLEL_UPDATES = 0

# Uptime jitters by a couple of seconds between polls; only move the
# timestamp when it changes materially (i.e. the bridge rebooted).
UPTIME_DEVIATION = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond sensor entities."""
    data = entry.runtime_data
    hub = data.hub

    entities: list[Entity] = [
        BondWifiRssiSensor(data),
        BondLastRestartSensor(data),
    ]
    entities.extend(
        BondRfFrequencySensor(data, device)
        for device in hub.devices
        if device.props.get("freq") is not None
    )
    async_add_entities(entities)


class BondWifiRssiSensor(BondHubEntity, SensorEntity):
    """Wi-Fi signal strength of the bridge itself."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "wifi_rssi"

    def __init__(self, data: BondData) -> None:
        """Initialize the sensor."""
        super().__init__(data, "wifi_rssi")

    @property
    def native_value(self) -> int | None:
        """Return the RSSI in dBm."""
        wifi = (self.coordinator.data or {}).get("wifi") or {}
        return wifi.get("rssi")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose network details alongside the signal reading."""
        wifi = (self.coordinator.data or {}).get("wifi") or {}
        return {
            key: wifi.get(key) for key in ("ip", "gw", "netmask", "dns") if key in wifi
        }


class BondLastRestartSensor(BondHubEntity, SensorEntity):
    """When the bridge last booted, derived from uptime_s."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_restart"

    def __init__(self, data: BondData) -> None:
        """Initialize the sensor."""
        super().__init__(data, "last_restart")
        self._last_restart: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        """Return the boot timestamp."""
        version = (self.coordinator.data or {}).get("version") or {}
        uptime_s = version.get("uptime_s")
        if uptime_s is None:
            return self._last_restart
        restart = dt_util.utcnow() - timedelta(seconds=uptime_s)
        if (
            self._last_restart is None
            or abs(restart - self._last_restart) > UPTIME_DEVIATION
        ):
            self._last_restart = restart
        return self._last_restart


class BondRfFrequencySensor(SensorEntity):
    """The RF carrier frequency a device is paired on (static diagnostic)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_native_unit_of_measurement = UnitOfFrequency.MEGAHERTZ
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False
    _attr_translation_key = "rf_frequency"

    def __init__(self, data: BondData, device: BondDevice) -> None:
        """Initialize the sensor from static device properties."""
        hub = data.hub
        self._attr_unique_id = f"{hub.bond_id}_{device.device_id}_rf_frequency"
        self._attr_device_info = bond_device_info(hub, device, data.hub_device_id)
        # The bridge reports freq in kHz.
        self._attr_native_value = device.props["freq"] / 1000
        self._attr_extra_state_attributes = {
            key: device.props[key]
            for key in ("bps", "zero_gap", "addr")
            if key in device.props
        }
