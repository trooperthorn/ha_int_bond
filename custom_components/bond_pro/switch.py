"""Support for Bond Pro generic devices."""

from __future__ import annotations

from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .bond_async_pro import Action, DeviceType
from .entity import BondEntity, BondHubEntity
from .models import BondData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond generic devices."""
    data = entry.runtime_data

    if data.telemetry.supports("bpup"):
        async_add_entities([BondBpupBroadcastSwitch(data)])
    async_add_entities(
        BondSwitch(data, device)
        for device in data.hub.entity_sources
        if DeviceType.is_generic(device.type)
    )


class BondSwitch(BondEntity, SwitchEntity):
    """Representation of a Bond generic device."""

    def _apply_state(self) -> None:
        self._attr_is_on = self._device.state.get("power") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._bond.action(self._device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._bond.action(self._device_id, Action.turn_off())

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the believed state to on or off."""
        try:
            await self._bond.action(
                self._device_id, Action.set_power_state_belief(power_state)
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_power_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex


class BondBpupBroadcastSwitch(BondHubEntity, SwitchEntity):
    """Broadcast all state updates on UDP 30007 (PATCH /v2/api/bpup).

    Off by default on the bridge.  Only needed by listeners that do not
    subscribe; the integration itself subscribes, so this stays disabled
    unless enabled in the entity registry.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "bpup_broadcast"

    def __init__(self, data: BondData) -> None:
        """Initialize the switch."""
        super().__init__(data, "bpup_broadcast")

    @property
    def is_on(self) -> bool | None:
        """Return the bridge's broadcast flag."""
        bpup = (self.coordinator.data or {}).get("bpup") or {}
        broadcast = bpup.get("broadcast")
        return None if broadcast is None else bool(broadcast)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable broadcast."""
        await self._bond.set_bpup_broadcast(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable broadcast."""
        await self._bond.set_bpup_broadcast(False)
        await self.coordinator.async_request_refresh()
