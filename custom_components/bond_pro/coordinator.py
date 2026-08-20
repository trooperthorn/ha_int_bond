"""Coordinators for the Bond Pro integration.

Two coordinators replace the upstream integration's per-entity timers:

- BondFallbackCoordinator sweeps device state as a single hub-level fallback
  when BPUP push is down (and slowly as a drift check while push is alive).
  Upstream scheduled one timer per entity, so a hub with 8 devices ran ~20
  timers and issued redundant HTTP requests.
- BondTelemetryCoordinator polls bridge telemetry (Wi-Fi RSSI, uptime,
  blue light) that has no push channel at all.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from .bond_async_pro import Bond, BPUPSubscriptions

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import (
    DOMAIN,
    FALLBACK_INTERVAL_BPUP_ALIVE,
    FALLBACK_INTERVAL_BPUP_DEAD,
    TELEMETRY_INTERVAL,
)
from .utils import MAX_REQUESTS, BondHub

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class BondFallbackCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch state for every hub device in one sweep.

    The data payload maps device_id -> state dict.  A device missing from the
    payload failed its last fetch and should be considered unavailable.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: BondHub,
        bpup_subs: BPUPSubscriptions,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {hub.bond_id} state",
            update_interval=FALLBACK_INTERVAL_BPUP_DEAD,
        )
        self.hub = hub
        self.bpup_subs = bpup_subs

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch state for all devices with limited concurrency."""
        devices = self.hub.devices
        results = await gather_with_limited_concurrency(
            MAX_REQUESTS,
            *(self.hub.bond.device_state(device.device_id) for device in devices),
            return_exceptions=True,
        )
        data: dict[str, dict[str, Any]] = {}
        errors = 0
        for device, result in zip(devices, results):
            if isinstance(result, Exception):
                errors += 1
                if not isinstance(result, (ClientError, TimeoutError, OSError)):
                    raise result
                _LOGGER.debug(
                    "Fetching state for %s failed: %s", device.device_id, result
                )
                continue
            device.state = result
            data[device.device_id] = result

        if devices and errors == len(devices):
            raise UpdateFailed("Unable to reach the Bond bridge")

        self._adjust_interval()
        return data

    def _adjust_interval(self) -> None:
        """Poll slowly while BPUP push is alive, quickly when it is not."""
        interval = (
            FALLBACK_INTERVAL_BPUP_ALIVE
            if self.bpup_subs.alive
            else FALLBACK_INTERVAL_BPUP_DEAD
        )
        if self.update_interval != interval:
            _LOGGER.debug("Fallback poll interval set to %s", interval)
            self.update_interval = interval


class BondTelemetryCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll bridge telemetry that is never pushed.

    Payload keys: "wifi" (sys/wifi/sta), "version" (sys/version) and
    "bridge" (bridge info, including bluelight).  Missing keys mean the
    bridge does not support that endpoint (e.g. Smart by Bond devices have
    no /v2/bridge).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        bond: Bond,
        hub: BondHub,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {hub.bond_id} telemetry",
            update_interval=TELEMETRY_INTERVAL,
        )
        self.bond = bond
        self.hub = hub

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch bridge telemetry."""
        data: dict[str, Any] = {}
        try:
            data["version"] = await self.bond.version()
            data["wifi"] = await self.bond.wifi_sta()
            if self.hub.is_bridge:
                data["bridge"] = await self.bond.bridge()
        except (ClientError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Unable to fetch bridge telemetry: {err}") from err
        return data
