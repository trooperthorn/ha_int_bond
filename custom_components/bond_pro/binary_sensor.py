"""Support for Bond Pro binary sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .entity import BondHubEntity
from .models import BondData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond binary sensor entities."""
    data = entry.runtime_data
    if data.telemetry.supports_faults:
        async_add_entities([BondFaultsBinarySensor(data)])


def controller_faults(data: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Return the controller fault list from a telemetry payload."""
    faults = (data or {}).get("faults")
    if faults is None:
        return None
    return (faults.get("controller") or {}).get("faults") or []


class BondFaultsBinarySensor(BondHubEntity, BinarySensorEntity):
    """On while the bridge controller has raised a fault (/v2/sys/faults)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "faults"

    def __init__(self, data: BondData) -> None:
        """Initialize the sensor."""
        super().__init__(data, "faults")

    @property
    def is_on(self) -> bool | None:
        """Return True when any fault is listed."""
        faults = controller_faults(self.coordinator.data)
        return None if faults is None else bool(faults)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose fault names and the lifetime raise count.

        The list may gain values in future firmware, so unknown fault names
        are passed through as-is rather than mapped.
        """
        faults = controller_faults(self.coordinator.data) or []
        controller = ((self.coordinator.data or {}).get("faults") or {}).get(
            "controller"
        ) or {}
        return {
            "faults": sorted(f.get("fault", "unknown") for f in faults),
            "raise_count": controller.get("raise_count"),
        }
