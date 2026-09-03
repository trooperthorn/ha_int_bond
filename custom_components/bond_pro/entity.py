"""An abstract class common to all Bond Pro entities."""

from __future__ import annotations

from abc import abstractmethod
import logging

from aiohttp import ClientError

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BondFallbackCoordinator, BondTelemetryCoordinator
from .models import BondData
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)


def hub_device_info(hub: BondHub) -> DeviceInfo:
    """Build the device registry entry for the hub itself."""
    return DeviceInfo(
        identifiers={(DOMAIN, hub.bond_id or hub.host)},
        manufacturer=hub.make,
        name=hub.name or hub.bond_id,
        model=hub.target,
        sw_version=hub.fw_ver,
        hw_version=hub.mcu_ver,
        suggested_area=hub.location,
        configuration_url=f"http://{hub.host}",
    )


def bond_device_info(
    hub: BondHub, device: BondDevice, hub_device_id: str
) -> DeviceInfo:
    """Build the device registry entry for a device behind the hub."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{hub.bond_id}_{device.device_id}")},
        manufacturer=hub.make,
        name=device.name,
        via_device_id=hub_device_id,
        configuration_url=f"http://{hub.host}",
    )
    if device.location is not None:
        device_info["suggested_area"] = device.location
    if not hub.is_bridge:
        # Smart by Bond: the device IS the hub hardware.
        if hub.model is not None:
            device_info["model"] = hub.model
        if hub.fw_ver is not None:
            device_info["sw_version"] = hub.fw_ver
        if hub.mcu_ver is not None:
            device_info["hw_version"] = hub.mcu_ver
    else:
        model_data = []
        if device.branding_profile:
            model_data.append(device.branding_profile)
        if device.template:
            model_data.append(device.template)
        if model_data:
            device_info["model"] = " ".join(model_data)
    return device_info


class BondEntity(CoordinatorEntity[BondFallbackCoordinator]):
    """Generic Bond entity encapsulating common features of any Bond device.

    State arrives via BPUP push (primary) and the hub-level fallback
    coordinator (secondary).  Neither path schedules per-entity timers.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        data: BondData,
        device: BondDevice,
        sub_device: str | None = None,
        sub_device_id: str | None = None,
    ) -> None:
        """Initialize entity with API and device info."""
        super().__init__(data.fallback)
        hub = data.hub
        self._hub = hub
        self._bond = hub.bond
        self._device = device
        self._device_id = device.device_id
        self._bpup_subs = data.bpup_subs
        if sub_device_id:
            sub_device_id = f"_{sub_device_id}"
        elif sub_device:
            sub_device_id = f"_{sub_device}"
        else:
            sub_device_id = ""
        self._attr_unique_id = f"{hub.bond_id}_{device.device_id}{sub_device_id}"
        if sub_device:
            self._attr_translation_key = sub_device
        else:
            # Main entity of the device: carries the device name.
            self._attr_name = None
        self._attr_assumed_state = hub.is_bridge and not device.trust_state
        self._attr_device_info = bond_device_info(hub, device, data.hub_device_id)
        self._attr_available = True
        self._apply_state()

    async def async_update(self) -> None:
        """Perform a manual update from API (homeassistant.update_entity)."""
        try:
            state: dict = await self._bond.device_state(self._device_id)
        except (ClientError, TimeoutError, OSError) as error:
            if self.available:
                _LOGGER.warning(
                    "Entity %s has become unavailable", self.entity_id, exc_info=error
                )
            self._attr_available = False
        else:
            self._async_state_callback(state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply state from the fallback coordinator sweep."""
        state = (self.coordinator.data or {}).get(self._device_id)
        if state is None:
            if self._attr_available:
                _LOGGER.warning("Entity %s has become unavailable", self.entity_id)
            self._attr_available = False
        else:
            self._async_state_callback(state)
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Available when the device answered its last poll or push is live."""
        return self._attr_available

    @abstractmethod
    def _apply_state(self) -> None:
        raise NotImplementedError

    @callback
    def _async_state_callback(self, state: dict) -> None:
        """Process a state change."""
        if not self._attr_available:
            _LOGGER.info("Entity %s has come back", self.entity_id)
        self._attr_available = True
        _LOGGER.debug(
            "Device state for %s (%s) is:\n%s", self.name, self.entity_id, state
        )
        self._device.state = state
        self._apply_state()

    @callback
    def _async_bpup_callback(self, json_msg: dict) -> None:
        """Process a state change from BPUP."""
        topic = json_msg["t"]
        if topic != f"devices/{self._device_id}/state":
            return

        self._async_state_callback(json_msg["b"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to BPUP on add."""
        await super().async_added_to_hass()
        self._bpup_subs.subscribe(self._device_id, self._async_bpup_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from BPUP data on remove."""
        await super().async_will_remove_from_hass()
        self._bpup_subs.unsubscribe(self._device_id, self._async_bpup_callback)


class BondHubEntity(CoordinatorEntity[BondTelemetryCoordinator]):
    """Base for entities that belong to the bridge itself."""

    _attr_has_entity_name = True

    def __init__(self, data: BondData, key: str) -> None:
        """Initialize the hub entity."""
        super().__init__(data.telemetry)
        self._hub = data.hub
        self._bond = data.hub.bond
        self._attr_unique_id = f"{data.hub.bond_id}_{key}"
        self._attr_device_info = hub_device_info(data.hub)
