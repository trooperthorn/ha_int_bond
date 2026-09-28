"""Support for Bond Pro numbers (new vs upstream)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .bond_async_pro import Action, DeviceType
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond number entities."""
    data = entry.runtime_data
    entities: list[NumberEntity] = [
        BondFlameNumber(data, device)
        for device in data.hub.entity_sources
        if DeviceType.is_fireplace(device.type) and device.supports_set_flame()
    ]
    entities.extend(
        BondHeatNumber(data, device)
        for device in data.hub.entity_sources
        if device.has_action(Action.SET_HEAT)
    )
    async_add_entities(entities)


class BondFlameNumber(BondEntity, NumberEntity):
    """Direct flame-level control for fireplaces (SetFlame)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
    _attr_translation_key = "flame"

    def __init__(self, data: BondData, device: BondDevice) -> None:
        """Initialize the flame number."""
        super().__init__(data, device, "flame")

    def _apply_state(self) -> None:
        self._attr_native_value = self._device.state.get("flame")

    async def async_set_native_value(self, value: float) -> None:
        """Set the flame level."""
        flame = round(value)
        if flame == 0:
            await self._bond.action(self._device_id, Action.turn_off())
            return
        await self._bond.action(self._device_id, Action.set_flame(flame))


class BondHeatNumber(BondEntity, NumberEntity):
    """Heat level for the Heat feature (SetHeat, 1-100).

    The bridge remembers heat while power is off, so 0 maps to TurnOff and
    the reported value is 0 whenever power is off.
    """

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
    _attr_translation_key = "heat"

    def __init__(self, data: BondData, device: BondDevice) -> None:
        """Initialize the heat number."""
        super().__init__(data, device, "heat")

    def _apply_state(self) -> None:
        state = self._device.state
        heat = state.get("heat")
        if heat is not None and state.get("power") == 0:
            heat = 0
        self._attr_native_value = heat

    async def async_set_native_value(self, value: float) -> None:
        """Set the heat level (SetHeat also turns power on)."""
        heat = round(value)
        if heat == 0:
            await self._bond.action(self._device_id, Action.turn_off())
            return
        await self._bond.action(self._device_id, Action(Action.SET_HEAT, heat))
