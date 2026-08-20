"""Support for Bond Pro buttons."""

from __future__ import annotations

from dataclasses import dataclass

from .bond_async_pro import Action

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice

PARALLEL_UPDATES = 0

# The api requires a step size even though it does not
# seem to matter what it is as the underlying device is likely
# getting an increase/decrease signal only
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

PRESET_BUTTON = BondButtonEntityDescription(
    key=Action.PRESET,
    translation_key="preset",
    mutually_exclusive=None,
    argument=None,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond button devices."""
    data = entry.runtime_data
    entities: list[BondButtonEntity] = []

    for device in data.hub.devices:
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
            # Most devices have the stop action available, but
            # we only add the stop action button if we add actions
            # since it's not so useful if there are no actions to stop
            device_entities.append(BondButtonEntity(data, device, STOP_BUTTON))
        if device.has_action(PRESET_BUTTON.key):
            device_entities.append(BondButtonEntity(data, device, PRESET_BUTTON))
        entities.extend(device_entities)

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
