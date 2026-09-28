"""Reusable utilities for the Bond Pro component."""

from __future__ import annotations

import logging
from typing import Any, cast

from aiohttp import ClientResponseError
from homeassistant.util.async_ import gather_with_limited_concurrency

from .bond_async_pro import Action, Bond, BondType
from .const import BRIDGE_MAKE

MAX_REQUESTS = 6

_LOGGER = logging.getLogger(__name__)


class BondDevice:
    """Helper device class to hold ID and attributes together."""

    def __init__(
        self,
        device_id: str,
        attrs: dict[str, Any],
        props: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Create a helper device from ID and attributes returned by API."""
        self.device_id = device_id
        self.props = props
        self.state = state
        self.attrs = attrs or {}
        self._supported_actions: set[str] = set(self.attrs.get("actions", []))

    def __repr__(self) -> str:
        """Return readable representation of a bond device."""
        return {
            "device_id": self.device_id,
            "props": self.props,
            "attrs": self.attrs,
            "state": self.state,
        }.__repr__()

    is_group = False

    @property
    def topic(self) -> str:
        """Return the BPUP topic carrying this device's state."""
        return f"devices/{self.device_id}/state"

    def api(self, bond: Bond) -> Bond | BondGroupApi:
        """Return the object entities send actions and state requests to."""
        return bond

    @property
    def name(self) -> str:
        """Get the name of this device."""
        return cast(str, self.attrs["name"])

    @property
    def type(self) -> str:
        """Get the type of this device."""
        return cast(str, self.attrs["type"])

    @property
    def location(self) -> str | None:
        """Get the location of this device."""
        return self.attrs.get("location")

    @property
    def template(self) -> str | None:
        """Return this model template."""
        return self.attrs.get("template")

    @property
    def branding_profile(self) -> str | None:
        """Return this branding profile."""
        return self.props.get("branding_profile")

    @property
    def trust_state(self) -> bool:
        """Check if Trust State is turned on."""
        return bool(self.props.get("trust_state", False))

    @property
    def supported_actions(self) -> set[str]:
        """Return the actions supported by this device."""
        return self._supported_actions

    def has_action(self, action: str) -> bool:
        """Check to see if the device supports an action."""
        return action in self._supported_actions

    def _has_any_action(self, actions: set[str]) -> bool:
        """Check to see if the device supports any of the actions."""
        return bool(self._supported_actions.intersection(actions))

    def supports_speed(self) -> bool:
        """Return True if this device supports any of the speed related commands."""
        return self._has_any_action({Action.SET_SPEED})

    def supports_direction(self) -> bool:
        """Return True if this device supports any of the direction related commands."""
        return self._has_any_action({Action.SET_DIRECTION})

    def supports_set_position(self) -> bool:
        """Return True if this device supports setting the position."""
        return self._has_any_action({Action.SET_POSITION})

    def open_action(self) -> str | None:
        """Return the action that opens this device.

        Some shades only expose Raise/Lower or Retract/Extend, which the
        bridge maps to Open/Close through open_raises/open_retracts.
        """
        return next(
            (
                action
                for action in (Action.OPEN, Action.RAISE, Action.RETRACT)
                if self.has_action(action)
            ),
            None,
        )

    def close_action(self) -> str | None:
        """Return the action that closes this device."""
        return next(
            (
                action
                for action in (Action.CLOSE, Action.LOWER, Action.EXTEND)
                if self.has_action(action)
            ),
            None,
        )

    def supports_open(self) -> bool:
        """Return True if this device supports opening."""
        return self.open_action() is not None

    def supports_close(self) -> bool:
        """Return True if this device supports closing."""
        return self.close_action() is not None

    def supports_set_tilt_position(self) -> bool:
        """Return True if this device supports SetTiltPosition (degrees)."""
        return self._has_any_action({Action.SET_TILT_POSITION})

    def supports_tilt_open(self) -> bool:
        """Return True if this device supports tilt opening."""
        return self._has_any_action({Action.TILT_OPEN})

    def supports_tilt_close(self) -> bool:
        """Return True if this device supports tilt closing."""
        return self._has_any_action({Action.TILT_CLOSE})

    def supports_hold(self) -> bool:
        """Return True if this device supports hold aka stop."""
        return self._has_any_action({Action.HOLD})

    def supports_light(self) -> bool:
        """Return True if this device supports any of the light related commands."""
        return self._has_any_action({Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF})

    def supports_up_light(self) -> bool:
        """Return true if the device has an up light."""
        return self._has_any_action({Action.TURN_UP_LIGHT_ON, Action.TURN_UP_LIGHT_OFF})

    def supports_down_light(self) -> bool:
        """Return true if the device has a down light."""
        return self._has_any_action(
            {Action.TURN_DOWN_LIGHT_ON, Action.TURN_DOWN_LIGHT_OFF}
        )

    def supports_set_brightness(self) -> bool:
        """Return True if this device supports setting a light brightness."""
        return self._has_any_action({Action.SET_BRIGHTNESS})

    def supports_set_color_temp(self) -> bool:
        """Return True if this device supports setting a light color temperature."""
        return self._has_any_action({Action.SET_COLOR_TEMP})

    def supports_set_flame(self) -> bool:
        """Return True if this device supports setting a flame level."""
        return self._has_any_action({Action.SET_FLAME})


class BondGroupApi:
    """Routes a group entity's action and state calls to /v2/groups.

    Entity platforms call ``action`` and ``device_state`` with an ID; for a
    group that ID is the group ID, so this lets every platform drive groups
    unchanged.
    """

    def __init__(self, bond: Bond) -> None:
        """Wrap the hub's Bond API."""
        self._bond = bond

    async def action(self, group_id: str, action: Action) -> None:
        """Execute an action on every member device (one request)."""
        await self._bond.group_action(group_id, action)

    async def device_state(self, group_id: str) -> dict:
        """Return the state variables common to every member device."""
        return await self._bond.group_state(group_id)


class BondGroup(BondDevice):
    """A Bond group, exposed like a device of its members' common type.

    Group state lists only variables shared by all members, with null where
    members differ.  Groups cannot take state-belief PATCHes.
    """

    is_group = True

    @property
    def topic(self) -> str:
        """Return the BPUP topic carrying this group's state."""
        return f"groups/{self.device_id}/state"

    def api(self, bond: Bond) -> Bond | BondGroupApi:
        """Route calls to the group endpoints."""
        return BondGroupApi(bond)

    @property
    def type(self) -> str:
        """Return the members' device type, or "" for mixed groups."""
        types = self.attrs.get("types") or []
        return types[0] if len(types) == 1 else ""

    @property
    def location(self) -> str | None:
        """Return the members' location when they share one."""
        locations = self.attrs.get("locations") or []
        return locations[0] if len(locations) == 1 else None

    @property
    def template(self) -> str | None:
        """Groups have no template."""
        return None


class BondHub:
    """Hub device representing Bond Bridge."""

    def __init__(self, bond: Bond, host: str) -> None:
        """Initialize Bond Hub."""
        self.bond: Bond = bond
        self.host = host
        self._bridge: dict[str, Any] = {}
        self._version: dict[str, Any] = {}
        self._devices: list[BondDevice] = []
        self._groups: list[BondGroup] = []
        self._scenes: dict[str, dict[str, Any]] = {}

    async def setup(self, max_devices: int | None = None) -> None:
        """Read hub version information."""
        self._version = await self.bond.version()
        _LOGGER.debug("Bond reported the following version info: %s", self._version)
        # Fetch all available devices using Bond API.
        device_ids = await self.bond.devices()
        self._devices = []
        setup_device_ids = []
        tasks = []
        for idx, device_id in enumerate(device_ids):
            if max_devices is not None and idx >= max_devices:
                break
            setup_device_ids.append(device_id)
            tasks.extend(
                [
                    self.bond.device(device_id),
                    self.bond.device_properties(device_id),
                    self.bond.device_state(device_id),
                ]
            )

        responses = await gather_with_limited_concurrency(MAX_REQUESTS, *tasks)
        response_idx = 0
        for device_id in setup_device_ids:
            self._devices.append(
                BondDevice(
                    device_id,
                    responses[response_idx],
                    responses[response_idx + 1],
                    responses[response_idx + 2],
                )
            )
            response_idx += 3

        _LOGGER.debug("Discovered Bond devices: %s", self._devices)
        await self._setup_groups()
        await self._setup_scenes()
        try:
            # Smart by bond devices do not have a bridge api call
            self._bridge = await self.bond.bridge()
        except ClientResponseError:
            self._bridge = {}
        _LOGGER.debug("Bond reported the following bridge info: %s", self._bridge)

    async def _setup_groups(self) -> None:
        """Fetch groups; products without group support answer 404."""
        try:
            group_ids = await self.bond.groups()
        except ClientResponseError:
            group_ids = []
        responses = await gather_with_limited_concurrency(
            MAX_REQUESTS,
            *(
                request
                for group_id in group_ids
                for request in (
                    self.bond.group(group_id),
                    self.bond.group_properties(group_id),
                    self.bond.group_state(group_id),
                )
            ),
        )
        self._groups = [
            BondGroup(group_id, *responses[idx * 3 : idx * 3 + 3])
            for idx, group_id in enumerate(group_ids)
        ]
        _LOGGER.debug("Discovered Bond groups: %s", self._groups)

    async def _setup_scenes(self) -> None:
        """Fetch scenes; products without scene support answer 404."""
        try:
            scene_ids = await self.bond.scenes()
        except ClientResponseError:
            scene_ids = []
        scenes = await gather_with_limited_concurrency(
            MAX_REQUESTS, *(self.bond.scene(scene_id) for scene_id in scene_ids)
        )
        self._scenes = dict(zip(scene_ids, scenes, strict=True))
        _LOGGER.debug("Discovered Bond scenes: %s", self._scenes)

    @property
    def bond_id(self) -> str | None:
        """Return unique Bond ID for this hub."""
        # Old firmwares are missing the bondid
        return self._version.get("bondid")

    @property
    def target(self) -> str | None:
        """Return this hub target."""
        return self._version.get("target")

    @property
    def model(self) -> str | None:
        """Return this hub model."""
        return self._version.get("model")

    @property
    def make(self) -> str:
        """Return this hub make."""
        return cast(str, self._version.get("make", BRIDGE_MAKE))

    @property
    def name(self) -> str:
        """Get the name of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].name
        return cast(str, self._bridge["name"])

    @property
    def location(self) -> str | None:
        """Get the location of this bridge."""
        if not self.is_bridge and self._devices:
            return self._devices[0].location
        return self._bridge.get("location")

    @property
    def fw_ver(self) -> str | None:
        """Return this hub firmware version."""
        return self._version.get("fw_ver")

    @property
    def mcu_ver(self) -> str | None:
        """Return this hub hardware version."""
        return self._version.get("mcu_ver")

    @property
    def uptime_s(self) -> int | None:
        """Return this hub's uptime in seconds as of the last version fetch."""
        return self._version.get("uptime_s")

    @property
    def bluelight(self) -> int | None:
        """Return the bridge ring light brightness (0-255)."""
        return self._bridge.get("bluelight")

    @property
    def version_info(self) -> dict[str, Any]:
        """Return the raw version payload."""
        return self._version

    @property
    def bridge_info(self) -> dict[str, Any]:
        """Return the raw bridge payload."""
        return self._bridge

    @property
    def devices(self) -> list[BondDevice]:
        """Return a list of all devices controlled by this hub."""
        return self._devices

    @property
    def groups(self) -> list[BondGroup]:
        """Return the groups defined on this hub."""
        return self._groups

    @property
    def scenes(self) -> dict[str, dict[str, Any]]:
        """Return scene metadata keyed by scene ID."""
        return self._scenes

    @property
    def entity_sources(self) -> list[BondDevice]:
        """Return devices followed by groups: everything entities wrap."""
        return [*self._devices, *self._groups]

    @property
    def is_bridge(self) -> bool:
        """Return if the Bond is a Bond Bridge."""
        bondid = self._version["bondid"]
        return bool(BondType.is_bridge_from_serial(bondid))
