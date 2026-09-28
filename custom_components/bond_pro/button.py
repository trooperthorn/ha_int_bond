"""Support for Bond Pro buttons."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .bond_async_pro import Action
from .entity import BondEntity, BondHubEntity
from .models import BondData
from .utils import BondDevice

PARALLEL_UPDATES = 0

# Required by the API but appears not to affect the device; see docs/protocol.md.
STEP_SIZE = 10


@dataclass(frozen=True, kw_only=True)
class BondButtonEntityDescription(ButtonEntityDescription):
    """Class to describe a Bond Button entity."""

    mutually_exclusive: Action | None
    argument: int | None


STOP_BUTTON = BondButtonEntityDescription(
    key=Action.STOP,
    translation_key="stop_actions",
    mutually_exclusive=None,
    argument=None,
)


BUTTONS: tuple[BondButtonEntityDescription, ...] = (
    BondButtonEntityDescription(
        key=Action.TOGGLE_POWER,
        translation_key="toggle_power",
        mutually_exclusive=Action.TURN_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_LIGHT,
        translation_key="toggle_light",
        mutually_exclusive=Action.TURN_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_BRIGHTNESS,
        translation_key="increase_brightness",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_BRIGHTNESS,
        translation_key="decrease_brightness",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_UP_LIGHT,
        translation_key="toggle_up_light",
        mutually_exclusive=Action.TURN_UP_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_DOWN_LIGHT,
        translation_key="toggle_down_light",
        mutually_exclusive=Action.TURN_DOWN_LIGHT_ON,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DIMMER,
        translation_key="start_dimmer",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_LIGHT_TEMP,
        translation_key="toggle_light_temp",
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_UP_LIGHT_DIMMER,
        translation_key="start_up_light_dimmer",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DOWN_LIGHT_DIMMER,
        translation_key="start_down_light_dimmer",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_INCREASING_BRIGHTNESS,
        translation_key="start_increasing_brightness",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.START_DECREASING_BRIGHTNESS,
        translation_key="start_decreasing_brightness",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_UP_LIGHT_BRIGHTNESS,
        translation_key="increase_up_light_brightness",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_UP_LIGHT_BRIGHTNESS,
        translation_key="decrease_up_light_brightness",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_DOWN_LIGHT_BRIGHTNESS,
        translation_key="increase_down_light_brightness",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_DOWN_LIGHT_BRIGHTNESS,
        translation_key="decrease_down_light_brightness",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_UP_LIGHT_BRIGHTNESS,
        translation_key="cycle_up_light_brightness",
        mutually_exclusive=Action.SET_UP_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_DOWN_LIGHT_BRIGHTNESS,
        translation_key="cycle_down_light_brightness",
        mutually_exclusive=Action.SET_DOWN_LIGHT_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.CYCLE_BRIGHTNESS,
        translation_key="cycle_brightness",
        mutually_exclusive=Action.SET_BRIGHTNESS,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_SPEED,
        translation_key="increase_speed",
        mutually_exclusive=Action.SET_SPEED,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_SPEED,
        translation_key="decrease_speed",
        mutually_exclusive=Action.SET_SPEED,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_DIRECTION,
        translation_key="toggle_direction",
        mutually_exclusive=Action.SET_DIRECTION,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_TEMPERATURE,
        translation_key="increase_temperature",
        mutually_exclusive=None,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_TEMPERATURE,
        translation_key="decrease_temperature",
        mutually_exclusive=None,
        argument=1,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_FLAME,
        translation_key="increase_flame",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_FLAME,
        translation_key="decrease_flame",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_OPEN,
        translation_key="toggle_open",
        mutually_exclusive=Action.OPEN,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.INCREASE_POSITION,
        translation_key="increase_position",
        mutually_exclusive=Action.SET_POSITION,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_POSITION,
        translation_key="decrease_position",
        mutually_exclusive=Action.SET_POSITION,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.OPEN_NEXT,
        translation_key="open_next",
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.CLOSE_NEXT,
        translation_key="close_next",
        mutually_exclusive=None,
        argument=None,
    ),
)

BUTTONS += (
    BondButtonEntityDescription(
        key=Action.INCREASE_HEAT,
        translation_key="increase_heat",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.DECREASE_HEAT,
        translation_key="decrease_heat",
        mutually_exclusive=None,
        argument=STEP_SIZE,
    ),
    BondButtonEntityDescription(
        key=Action.HEAT_PRESET_NEXT,
        translation_key="heat_preset_next",
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.HEAT_PRESET_PREV,
        translation_key="heat_preset_prev",
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.TOGGLE_TILT,
        translation_key="toggle_tilt",
        mutually_exclusive=None,
        argument=None,
    ),
)

PRESET_BUTTON = BondButtonEntityDescription(
    key=Action.PRESET,
    translation_key="preset",
    mutually_exclusive=None,
    argument=None,
)

# Pair feature. These change the appliance's address table and need the
# appliance in pairing mode (except UnpairSelf), so they are config buttons
# and disabled by default. On devices without Unpair, Pair toggles.
PAIRING_BUTTONS: tuple[BondButtonEntityDescription, ...] = (
    BondButtonEntityDescription(
        key=Action.PAIR,
        translation_key="pair",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.UNPAIR,
        translation_key="unpair",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mutually_exclusive=None,
        argument=None,
    ),
    BondButtonEntityDescription(
        key=Action.UNPAIR_SELF,
        translation_key="unpair_self",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        mutually_exclusive=None,
        argument=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond button devices."""
    data = entry.runtime_data
    entities: list[ButtonEntity] = []

    for device in data.hub.entity_sources:
        device_entities = [
            BondButtonEntity(data, device, description)
            for description in BUTTONS
            if device.has_action(description.key)
            and (
                description.mutually_exclusive is None
                or not device.has_action(description.mutually_exclusive)
            )
        ]
        if device_entities and device.has_action(STOP_BUTTON.key):
            # Only useful when the device also has other action buttons to stop.
            device_entities.append(BondButtonEntity(data, device, STOP_BUTTON))
        if device.has_action(PRESET_BUTTON.key):
            device_entities.append(BondButtonEntity(data, device, PRESET_BUTTON))
        device_entities.extend(
            BondButtonEntity(data, device, description)
            for description in PAIRING_BUTTONS
            if not device.is_group and device.has_action(description.key)
        )
        entities.extend(device_entities)

    if data.telemetry.supports_faults:
        entities.append(BondClearFaultsButton(data))
    entities.append(BondRebootButton(data))
    if data.telemetry.supports("indicate"):
        entities.append(BondIdentifyButton(data))

    async_add_entities(entities)


class BondButtonEntity(BondEntity, ButtonEntity):
    """Bond Button Device."""

    entity_description: BondButtonEntityDescription

    def __init__(
        self,
        data: BondData,
        device: BondDevice,
        description: BondButtonEntityDescription,
    ) -> None:
        """Init Bond button."""
        self.entity_description = description
        super().__init__(
            data, device, description.translation_key, description.key.lower()
        )

    async def async_press(self) -> None:
        """Press the button."""
        description = self.entity_description
        key = description.key
        if argument := description.argument:
            action = Action(key, argument)
        else:
            action = Action(key)
        await self._bond.action(self._device_id, action)

    def _apply_state(self) -> None:
        """Buttons are stateless."""


class BondClearFaultsButton(BondHubEntity, ButtonEntity):
    """Clear bridge controller faults that need a manual clear."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "clear_faults"

    def __init__(self, data: BondData) -> None:
        """Initialize the button."""
        super().__init__(data, "clear_faults")

    async def async_press(self) -> None:
        """Send the clear; the bridge applies it asynchronously."""
        await self._bond.clear_faults()
        await self.coordinator.async_request_refresh()


class BondRebootButton(BondHubEntity, ButtonEntity):
    """Restart the bridge (PUT /v2/sys/reboot)."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: BondData) -> None:
        """Initialize the button."""
        super().__init__(data, "reboot")

    async def async_press(self) -> None:
        """Reboot the bridge; BPUP and polling recover on their own."""
        await self._bond.reboot()


# Seconds of identify animation per press (the bridge allows 0-30).
IDENTIFY_SECONDS = 10


class BondIdentifyButton(BondHubEntity, ButtonEntity):
    """Play the identify animation (PATCH /v2/sys/indicate, MT-1500)."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, data: BondData) -> None:
        """Initialize the button."""
        super().__init__(data, "identify")

    async def async_press(self) -> None:
        """Start the animation."""
        await self._bond.set_indicate(IDENTIFY_SECONDS)
