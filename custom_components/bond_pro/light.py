"""Support for Bond Pro lights."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from .bond_async_pro import Action, DeviceType

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .entity import BondEntity, BondHubEntity
from .models import BondData
from .utils import BondDevice

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond light devices."""
    data = entry.runtime_data
    hub = data.hub

    fan_lights: list[Entity] = [
        BondLight(data, device, "light")
        for device in hub.devices
        if DeviceType.is_fan(device.type)
        and device.supports_light()
        and not (device.supports_up_light() and device.supports_down_light())
    ]

    fan_up_lights: list[Entity] = [
        BondUpLight(data, device, "up_light")
        for device in hub.devices
        if DeviceType.is_fan(device.type) and device.supports_up_light()
    ]

    fan_down_lights: list[Entity] = [
        BondDownLight(data, device, "down_light")
        for device in hub.devices
        if DeviceType.is_fan(device.type) and device.supports_down_light()
    ]

    fireplaces: list[Entity] = [
        BondFireplace(data, device)
        for device in hub.devices
        if DeviceType.is_fireplace(device.type)
    ]

    fp_lights: list[Entity] = [
        BondLight(data, device, "light")
        for device in hub.devices
        if DeviceType.is_fireplace(device.type) and device.supports_light()
    ]

    lights: list[Entity] = [
        BondLight(data, device)
        for device in hub.devices
        if DeviceType.is_light(device.type)
    ]

    entities = (
        fan_lights + fan_up_lights + fan_down_lights + fireplaces + fp_lights + lights
    )
    if hub.is_bridge and hub.bluelight is not None:
        entities.append(BondBlueLight(data))

    async_add_entities(entities)


class BondBaseLight(BondEntity, LightEntity):
    """Representation of a Bond light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_set_brightness_belief(self, brightness: int) -> None:
        """Set the belief state of the light."""
        if not self._device.supports_set_brightness():
            raise HomeAssistantError("This device does not support setting brightness")
        if brightness == 0:
            await self.async_set_power_belief(False)
            return
        try:
            await self._bond.action(
                self._device_id,
                Action.set_brightness_belief(round((brightness * 100) / 255)),
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_brightness_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the belief state of the light."""
        try:
            await self._bond.action(
                self._device_id, Action.set_light_state_belief(power_state)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_light_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex


class BondLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond light."""

    def __init__(
        self,
        data: BondData,
        device: BondDevice,
        sub_device: str | None = None,
    ) -> None:
        """Create HA entity representing Bond light."""
        super().__init__(data, device, sub_device)
        if device.supports_set_color_temp():
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_min_color_temp_kelvin = (
                device.props.get("min_color_temp") or self._attr_min_color_temp_kelvin
            )
            self._attr_max_color_temp_kelvin = (
                device.props.get("max_color_temp") or self._attr_max_color_temp_kelvin
            )
        elif device.supports_set_brightness():
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def _apply_state(self) -> None:
        state = self._device.state
        self._attr_is_on = state.get("light") == 1
        brightness = state.get("brightness")
        self._attr_brightness = round(brightness * 255 / 100) if brightness else None
        color_temp_kelvin = state.get("color_temp")
        # API resolution is 100K
        self._attr_color_temp_kelvin = (
            round(color_temp_kelvin, -2) if color_temp_kelvin else None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        basic_on = True

        if brightness := kwargs.get(ATTR_BRIGHTNESS):
            await self._bond.action(
                self._device_id,
                Action.set_brightness(round((brightness * 100) / 255)),
            )
            basic_on = False

        if color_temp := kwargs.get(ATTR_COLOR_TEMP_KELVIN):
            await self._bond.action(
                self._device_id,
                # API resolution is 100K
                Action.set_color_temperature(round(color_temp, -2)),
            )
            basic_on = False

        if basic_on:
            await self._bond.action(self._device_id, Action.turn_light_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._bond.action(self._device_id, Action.turn_light_off())


class BondDownLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond down light."""

    def _apply_state(self) -> None:
        state = self._device.state
        self._attr_is_on = bool(state.get("down_light") and state.get("light"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._bond.action(self._device_id, Action(Action.TURN_DOWN_LIGHT_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._bond.action(self._device_id, Action(Action.TURN_DOWN_LIGHT_OFF))


class BondUpLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond up light."""

    def _apply_state(self) -> None:
        state = self._device.state
        self._attr_is_on = bool(state.get("up_light") and state.get("light"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._bond.action(self._device_id, Action(Action.TURN_UP_LIGHT_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._bond.action(self._device_id, Action(Action.TURN_UP_LIGHT_OFF))


class BondFireplace(BondEntity, LightEntity):
    """Representation of a Bond-controlled fireplace."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def _apply_state(self) -> None:
        state = self._device.state
        power = state.get("power")
        flame = state.get("flame")
        self._attr_is_on = power == 1
        self._attr_brightness = round(flame * 255 / 100) if flame else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fireplace on."""
        if brightness := kwargs.get(ATTR_BRIGHTNESS):
            flame = round((brightness * 100) / 255)
            await self._bond.action(self._device_id, Action.set_flame(flame))
        else:
            await self._bond.action(self._device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fireplace off."""
        await self._bond.action(self._device_id, Action.turn_off())

    async def async_set_brightness_belief(self, brightness: int) -> None:
        """Set the belief state of the flame."""
        if not self._device.supports_set_brightness():
            raise HomeAssistantError("This device does not support setting brightness")
        if brightness == 0:
            await self.async_set_power_belief(False)
            return
        try:
            await self._bond.action(
                self._device_id,
                Action.set_brightness_belief(round((brightness * 100) / 255)),
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_brightness_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the belief state of the fireplace."""
        try:
            await self._bond.action(
                self._device_id, Action.set_power_state_belief(power_state)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_power_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex


class BondBlueLight(BondHubEntity, LightEntity):
    """The blue ring light on the Bond Bridge itself (new vs upstream)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "blue_light"

    def __init__(self, data: BondData) -> None:
        """Initialize the bridge ring light."""
        super().__init__(data, "bluelight")

    @property
    def _bluelight(self) -> int | None:
        data = self.coordinator.data or {}
        bridge = data.get("bridge") or {}
        bluelight = bridge.get("bluelight")
        if bluelight is None:
            bluelight = self._hub.bluelight
        return bluelight

    @property
    def is_on(self) -> bool | None:
        """Return True when the ring light has any brightness."""
        bluelight = self._bluelight
        return None if bluelight is None else bluelight > 0

    @property
    def brightness(self) -> int | None:
        """Return the ring light brightness (0-255)."""
        return self._bluelight

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the ring light brightness."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        await self._bond.set_bluelight_brightness(brightness)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ring light off."""
        await self._bond.set_bluelight_brightness(0)
        await self.coordinator.async_request_refresh()
