"""Support for Bond Pro covers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .bond_async_pro import Action, DeviceType
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice

PARALLEL_UPDATES = 0


def _bond_to_hass_position(bond_position: int) -> int:
    """Convert bond 0-open 100-closed to hass 0-closed 100-open."""
    return abs(bond_position - 100)


def _hass_to_bond_position(hass_position: int) -> int:
    """Convert hass 0-closed 100-open to bond 0-open 100-closed."""
    return 100 - hass_position


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond cover devices."""
    data = entry.runtime_data
    entities: list[CoverEntity] = []
    for device in data.hub.entity_sources:
        if device.type != DeviceType.MOTORIZED_SHADES:
            continue
        entities.append(BondCover(data, device))
        entities.extend(
            BondLayerCover(data, device, layer)
            for layer in LAYERS
            if device.has_action(layer.set_action)
        )
    async_add_entities(entities)


@dataclass(frozen=True)
class CoverLayer:
    """One independently positioned part of a shade (a rail or fabric)."""

    key: str
    state_key: str
    set_action: str
    open_action: str | None = None
    close_action: str | None = None


# Rails use 0 = open, 100 = closed like Position; raising a rail opens it.
LAYERS: tuple[CoverLayer, ...] = (
    CoverLayer(
        "upper_rail",
        "upper_rail_position",
        Action.SET_UPPER_RAIL_POSITION,
        Action.RAISE_UPPER_RAIL,
        Action.LOWER_UPPER_RAIL,
    ),
    CoverLayer(
        "lower_rail",
        "lower_rail_position",
        Action.SET_LOWER_RAIL_POSITION,
        Action.RAISE_LOWER_RAIL,
        Action.LOWER_LOWER_RAIL,
    ),
    CoverLayer("sheer", "sheer_position", Action.SET_SHEER_POSITION),
    CoverLayer("blackout", "blackout_position", Action.SET_BLACKOUT_POSITION),
)


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(self, data: BondData, device: BondDevice) -> None:
        """Create HA entity representing Bond cover."""
        super().__init__(data, device)
        supported_features = CoverEntityFeature(0)
        if self._device.supports_set_position():
            supported_features |= CoverEntityFeature.SET_POSITION
        if self._device.supports_open():
            supported_features |= CoverEntityFeature.OPEN
        if self._device.supports_close():
            supported_features |= CoverEntityFeature.CLOSE
        if self._device.supports_tilt_open():
            supported_features |= CoverEntityFeature.OPEN_TILT
        if self._device.supports_tilt_close():
            supported_features |= CoverEntityFeature.CLOSE_TILT
        if self._device.supports_set_tilt_position():
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        if self._device.supports_hold():
            if self._device.supports_open() or self._device.supports_close():
                supported_features |= CoverEntityFeature.STOP
            if self._device.supports_tilt_open() or self._device.supports_tilt_close():
                supported_features |= CoverEntityFeature.STOP_TILT
        self._attr_supported_features = supported_features

    def _apply_state(self) -> None:
        state = self._device.state
        cover_open = state.get("open")
        self._attr_is_closed = None if cover_open is None else cover_open == 0
        if (bond_position := state.get("position")) is not None:
            self._attr_current_cover_position = _bond_to_hass_position(bond_position)
        if (tilt := state.get("tilt_position")) is not None:
            min_tilt, max_tilt = self._tilt_range
            self._attr_current_cover_tilt_position = round(
                (tilt - min_tilt) * 100 / (max_tilt - min_tilt)
            )

    @property
    def _tilt_range(self) -> tuple[int, int]:
        """Return the tilt range in degrees (TiltPosition properties)."""
        props = self._device.props
        min_tilt = props.get("min_tilt", 0)
        max_tilt = props.get("max_tilt", 90)
        if max_tilt == min_tilt:
            max_tilt = min_tilt + 90
        return min_tilt, max_tilt

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the tilt, scaling HA's 0-100 onto min_tilt..max_tilt degrees."""
        min_tilt, max_tilt = self._tilt_range
        degrees = round(
            min_tilt + kwargs[ATTR_TILT_POSITION] * (max_tilt - min_tilt) / 100
        )
        await self._bond.action(
            self._device_id, Action(Action.SET_TILT_POSITION, degrees)
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        await self._bond.action(
            self._device_id,
            Action.set_position(_hass_to_bond_position(kwargs[ATTR_POSITION])),
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._bond.action(
            self._device_id, Action(self._device.open_action())
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._bond.action(
            self._device_id, Action(self._device.close_action())
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Hold cover."""
        await self._bond.action(self._device_id, Action.hold())

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._bond.action(self._device_id, Action.tilt_open())

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._bond.action(self._device_id, Action.tilt_close())

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._bond.action(self._device_id, Action.hold())


class BondLayerCover(BondEntity, CoverEntity):
    """A top-down/bottom-up rail or a sheer/blackout layer of a shade."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self, data: BondData, device: BondDevice, layer: CoverLayer
    ) -> None:
        """Create the layer entity."""
        self._layer = layer
        super().__init__(data, device, layer.key)
        supported_features = CoverEntityFeature.SET_POSITION
        if layer.open_action and device.has_action(layer.open_action):
            supported_features |= CoverEntityFeature.OPEN
        if layer.close_action and device.has_action(layer.close_action):
            supported_features |= CoverEntityFeature.CLOSE
        self._attr_supported_features = supported_features

    def _apply_state(self) -> None:
        bond_position = self._device.state.get(self._layer.state_key)
        if bond_position is None:
            self._attr_current_cover_position = None
            self._attr_is_closed = None
            return
        self._attr_current_cover_position = _bond_to_hass_position(bond_position)
        self._attr_is_closed = bond_position == 100

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the layer position."""
        await self._bond.action(
            self._device_id,
            Action(
                self._layer.set_action,
                _hass_to_bond_position(kwargs[ATTR_POSITION]),
            ),
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Raise the rail."""
        assert self._layer.open_action is not None
        await self._bond.action(self._device_id, Action(self._layer.open_action))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Lower the rail."""
        assert self._layer.close_action is not None
        await self._bond.action(self._device_id, Action(self._layer.close_action))
