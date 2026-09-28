"""Bond Local API wrapper."""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from typing import Any

import orjson
from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import (
    ClientConnectorError,
    ClientOSError,
    ServerDisconnectedError,
)

from .action import Action
from .bond_type import BondType
from .requestor_uuid import RequestorUUID


class Bond:
    """Bond API."""

    def __init__(
        self,
        host: str,
        token: str,
        requestor_uuid: RequestorUUID = RequestorUUID.ANONYMOUS,
        *,
        session: ClientSession | None = None,
        timeout: ClientTimeout | None = None,
    ):
        """Initialize Bond with provided host and token."""
        if not requestor_uuid.is_allowed():
            raise ValueError(
                f"Requestor UUID {requestor_uuid} is not allowed. Please use a "
                f"requestor UUID with a number greater than 0xA0."
            )
        self._requestor_uuid = requestor_uuid
        self._session_uuid = uuid.uuid4().hex[:4]
        self._host = host
        self._token = token
        self._timeout = timeout
        self._session = session

    async def version(self) -> dict:
        """Return the version of Bond reported by API."""
        return await self.__get("/v2/sys/version")

    async def bond_type(self) -> BondType:
        """Return the BondType based on the serial number reported by API."""
        version = await self.version()
        return BondType.from_serial(version["bondid"])

    async def token(self) -> dict:
        """Return the token after power reset or proof of ownership event."""
        return await self.__get("/v2/token")

    async def bridge(self) -> dict:
        """Return the name and location of the bridge."""
        return await self.__get("/v2/bridge")

    async def set_bridge(self, patch: dict) -> None:
        """Change bridge info (e.g. name, location, bluelight)."""
        await self.__patch("/v2/bridge", patch)

    async def set_bluelight_brightness(self, brightness: int) -> None:
        """Set the brightness of the blue light on the bridge (0..255)."""
        if brightness < 0 or brightness > 255:
            raise ValueError("Brightness must be between 0 and 255")
        await self.__patch("/v2/bridge", {"bluelight": brightness})

    async def sys_time(self) -> dict:
        """Return time and timezone settings."""
        return await self.__get("/v2/sys/time")

    async def sys_locale(self) -> dict:
        """Return the RF compliance region settings."""
        return await self.__get("/v2/sys/locale")

    async def wifi_sta(self) -> dict:
        """Return current Wi-Fi station settings including RSSI (dBm)."""
        return await self.__get("/v2/sys/wifi/sta")

    async def wifi_watchdog(self) -> dict:
        """Return the network watchdog configuration."""
        return await self.__get("/v2/sys/wifi/watchdog")

    async def set_wifi_watchdog(self, patch: dict) -> None:
        """Configure the network watchdog (rwdg_disable, rwdg_timer_ms)."""
        await self.__patch("/v2/sys/wifi/watchdog", patch)

    async def upgrade_status(self) -> dict:
        """Return the status of any running firmware upgrade."""
        return await self.__get("/v2/sys/upgrade")

    async def start_upgrade(self) -> None:
        """Start a firmware upgrade to the latest available version."""
        await self.__put("/v2/sys/upgrade", {})

    async def backup_status(self) -> dict:
        """Return the status of any running backup or restore."""
        return await self.__get("/v2/sys/backup")

    async def faults(self) -> dict:
        """Return the controller fault summary.

        Raises a 404 ClientResponseError on products without fault reporting.
        """
        return await self.__get("/v2/sys/faults")

    async def clear_faults(self) -> None:
        """Clear faults that need a manual clear (applied asynchronously)."""
        await self.__patch("/v2/sys/faults", {"clear": True})

    async def indicate(self) -> dict:
        """Return seconds left on the identify/commit animations (MT-1500)."""
        return await self.__get("/v2/sys/indicate")

    async def set_indicate(self, seconds: int) -> None:
        """Run the identify animation for 0-30 s (0 cancels)."""
        if seconds < 0 or seconds > 30:
            raise ValueError("Identify duration must be between 0 and 30")
        await self.__patch("/v2/sys/indicate", {"identify": seconds})

    async def power(self) -> dict:
        """Return power supply and temperature readings (404 if unsupported)."""
        return await self.__get("/v2/sys/power")

    async def vitals(self) -> dict:
        """Return usage counters (Mate Pro MT-1500, v4.28+)."""
        return await self.__get("/v2/sys/vitals")

    async def eth(self) -> dict:
        """Return Ethernet settings (404 when the product has no Ethernet)."""
        return await self.__get("/v2/sys/eth")

    async def set_bpup_broadcast(self, broadcast: bool) -> None:
        """Enable or disable broadcasting all state updates on port 30007."""
        await self.__patch("/v2/api/bpup", {"broadcast": broadcast})

    async def reboot(self) -> None:
        """Reboot the Bond."""
        await self.__put("/v2/sys/reboot", {})

    async def bpup_config(self) -> dict:
        """Return the BPUP transport configuration."""
        return await self.__get("/v2/api/bpup")

    async def set_bpup_config(self, patch: dict) -> None:
        """Configure the BPUP transport (e.g. {"broadcast": True})."""
        await self.__patch("/v2/api/bpup", patch)

    async def mqtt_config(self) -> dict:
        """Return the native MQTT transport configuration."""
        return await self.__get("/v2/api/mqtt")

    async def set_mqtt_config(self, patch: dict) -> None:
        """Configure the native MQTT transport (host, port, enabled...)."""
        await self.__patch("/v2/api/mqtt", patch)

    async def bhk_config(self) -> dict:
        """Return the Bond HomeKit integration configuration."""
        return await self.__get("/v2/api/bhk")

    async def signal_rssi(self) -> dict:
        """Return an RF noise scan: {"format": ["freq","rssi"], "results": [...]}."""
        return await self.__get("/v2/signal/rssi")

    async def devices(self) -> list[str]:
        """Return the list of available device IDs reported by API."""
        json = await self.__get("/v2/devices")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def device(self, device_id: str) -> dict:
        """Return main device metadata reported by API."""
        return await self.__get(f"/v2/devices/{device_id}")

    async def device_properties(self, device_id: str) -> dict:
        """Return device properties reported by API."""
        return await self.__get(f"/v2/devices/{device_id}/properties")

    async def device_state(self, device_id: str) -> dict:
        """Return current device state reported by API."""
        return await self.__get(f"/v2/devices/{device_id}/state")

    async def device_skeds(self, device_id: str) -> dict:
        """Return current device schedules reported by API."""
        return await self.__get(f"/v2/devices/{device_id}/skeds")

    async def device_sked(self, device_id: str, sked_id: str) -> dict:
        """Return one device schedule."""
        return await self.__get(f"/v2/devices/{device_id}/skeds/{sked_id}")

    async def set_device_sked(self, device_id: str, sked_id: str, patch: dict) -> None:
        """Modify a device schedule (e.g. {"enabled": 0})."""
        await self.__patch(f"/v2/devices/{device_id}/skeds/{sked_id}", patch)

    async def power_cycle_state(self, device_id: str) -> dict:
        """Return the Power Cycle State (bulb-recovery behavior) of a device."""
        return await self.__get(f"/v2/devices/{device_id}/power_cycle_state")

    async def set_power_cycle_state(self, device_id: str, patch: dict) -> None:
        """Update the Power Cycle State of a device."""
        await self.__patch(f"/v2/devices/{device_id}/power_cycle_state", patch)

    async def device_commands(self, device_id: str) -> list[str]:
        """Return the list of command IDs stored for a device."""
        json = await self.__get(f"/v2/devices/{device_id}/commands")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def device_command(self, device_id: str, command_id: str) -> dict:
        """Return one stored command (name, action, feedback, etc.)."""
        return await self.__get(f"/v2/devices/{device_id}/commands/{command_id}")

    async def device_command_signal(self, device_id: str, command_id: str) -> dict:
        """Return the raw RF/IR signal associated with a stored command."""
        return await self.__get(
            f"/v2/devices/{device_id}/commands/{command_id}/signal"
        )

    async def transmit_command(self, device_id: str, command_id: str) -> None:
        """Transmit a stored command's signal directly (bypasses state logic)."""
        await self.__put(f"/v2/devices/{device_id}/commands/{command_id}/tx", {})

    async def action(self, device_id: str, action: Action) -> None:
        """Execute given action for a given device."""
        if action.name == Action.SET_STATE_BELIEF:
            await self.__patch(f"/v2/devices/{device_id}/state", action.argument)
        else:
            await self.__put(
                f"/v2/devices/{device_id}/actions/{action.name}", action.argument
            )

    async def reload_device(self, device_id: str) -> None:
        """Rebuild a templated device's default commands.

        Overwrites command customisations; state and properties are kept.
        """
        await self.__put(f"/v2/devices/{device_id}/reload", {})

    async def scenes(self) -> list[str]:
        """Return the list of scene IDs."""
        json = await self.__get("/v2/scenes")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def scene(self, scene_id: str) -> dict:
        """Return scene metadata (name, actors, types, locations)."""
        return await self.__get(f"/v2/scenes/{scene_id}")

    async def run_scene(self, scene_id: str) -> None:
        """Run a scene; each actor is executed individually."""
        await self.__put(f"/v2/scenes/{scene_id}/run", {})

    async def channels(self) -> list[str]:
        """Return channel IDs (Mate Pro MT-1500, Sidekick Blue SKS-500-B)."""
        json = await self.__get("/v2/channels")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def channel(self, channel_id: str) -> dict:
        """Return a channel's settings."""
        return await self.__get(f"/v2/channels/{channel_id}")

    async def channel_action(self, channel_id: str, action: Action) -> None:
        """Execute an action on a channel."""
        await self.__put(
            f"/v2/channels/{channel_id}/actions/{action.name}", action.argument
        )

    async def skeds(self, kind: str, owner_id: str) -> dict[str, dict]:
        """Return every sked of a device, group, scene or channel by sked ID."""
        json = await self.__get(f"/v2/{kind}/{owner_id}/skeds")
        sked_ids = [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]
        return {
            sked_id: await self.__get(f"/v2/{kind}/{owner_id}/skeds/{sked_id}")
            for sked_id in sked_ids
        }

    async def create_sked(self, kind: str, owner_id: str, sked: dict) -> dict:
        """Create a sked; returns {"_id": ...}."""
        return await self.__post(f"/v2/{kind}/{owner_id}/skeds", sked)

    async def update_sked(
        self, kind: str, owner_id: str, sked_id: str, patch: dict
    ) -> None:
        """Change fields of an existing sked."""
        await self.__patch(f"/v2/{kind}/{owner_id}/skeds/{sked_id}", patch)

    async def delete_sked(self, kind: str, owner_id: str, sked_id: str) -> None:
        """Delete a sked."""
        await self.__delete(f"/v2/{kind}/{owner_id}/skeds/{sked_id}")

    async def sidekicks(self) -> list[str]:
        """Return the list of paired Sidekick remote IDs."""
        json = await self.__get("/v2/sidekicks")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def sidekick_learn_status(self) -> dict:
        """Return the Sidekick learn-window status."""
        return await self.__get("/v2/sidekicks/_learn")

    async def supports_groups(self) -> bool:
        """Return True if the Bond supports the Groups feature."""
        json = await self.__get("/v2/")
        return "groups" in json

    async def groups(self) -> list[str]:
        """Return the list of available group IDs reported by API."""
        json = await self.__get("/v2/groups")
        return [
            key
            for key in json
            if not key.startswith("_") and isinstance(json[key], dict)
        ]

    async def group(self, group_id: str) -> dict:
        """Return main group metadata reported by API."""
        return await self.__get(f"/v2/groups/{group_id}")

    async def group_properties(self, group_id: str) -> dict:
        """Return group properties reported by API."""
        return await self.__get(f"/v2/groups/{group_id}/properties")

    async def group_state(self, group_id: str) -> dict:
        """Return current group state reported by API."""
        return await self.__get(f"/v2/groups/{group_id}/state")

    async def group_skeds(self, group_id: str) -> dict:
        """Return current group schedules reported by API."""
        return await self.__get(f"/v2/groups/{group_id}/skeds")

    async def group_action(self, group_id: str, action: Action) -> None:
        """Execute given action for a given group."""
        if action.name == Action.SET_STATE_BELIEF:
            raise ValueError("Group state cannot be PATCHed")
        await self.__put(
            f"/v2/groups/{group_id}/actions/{action.name}", action.argument
        )

    def __request_kwargs(self) -> dict:
        """Build per-request kwargs with fresh headers.

        Headers are built per request so concurrent requests never share a
        mutable dict (the upstream library mutated one dict across in-flight
        requests, which could mis-tag BOND-UUID message IDs).
        """
        kwargs: dict = {
            "headers": {
                "BOND-Token": self._token,
                "BOND-UUID": self.__create_message_id(),
            }
        }
        if self._timeout:
            kwargs["timeout"] = self._timeout
        return kwargs

    async def __get(self, path: str) -> dict:
        async def get(session: ClientSession) -> dict:
            async with session.get(
                f"http://{self._host}{path}", **self.__request_kwargs()
            ) as response:
                response.raise_for_status()
                if response.status == 204:
                    # Documented for /v2/sys/upgrade and /v2/sys/backup.
                    return {}
                return await response.json(loads=orjson.loads)

        return await self.__call(get, idempotent=True)

    async def __patch(self, path: str, json: Any) -> None:
        async def patch(session: ClientSession) -> None:
            async with session.patch(
                f"http://{self._host}{path}", **self.__request_kwargs(), json=json
            ) as response:
                response.raise_for_status()

        await self.__call(patch)

    async def __post(self, path: str, json: Any) -> dict:
        async def post(session: ClientSession) -> dict:
            async with session.post(
                f"http://{self._host}{path}", **self.__request_kwargs(), json=json
            ) as response:
                response.raise_for_status()
                return await response.json(loads=orjson.loads)

        return await self.__call(post)

    async def __delete(self, path: str) -> None:
        async def delete(session: ClientSession) -> None:
            async with session.delete(
                f"http://{self._host}{path}", **self.__request_kwargs()
            ) as response:
                response.raise_for_status()

        await self.__call(delete)

    async def __put(self, path: str, json: Any) -> None:
        async def put(session: ClientSession) -> None:
            async with session.put(
                f"http://{self._host}{path}", **self.__request_kwargs(), json=json
            ) as response:
                response.raise_for_status()

        await self.__call(put)

    async def __call(
        self, handler: Callable[[ClientSession], Any], idempotent: bool = False
    ):
        if not self._session:
            async with ClientSession() as request_session:
                return await handler(request_session)
        else:
            try:
                return await handler(self._session)
            except (ClientOSError, ServerDisconnectedError) as err:
                # bond has a short connection close time so a reused idle
                # connection can drop. Unless the connect itself failed, the
                # bond may already have run the request, so only replay reads
                # (a replayed Toggle* action would flip the device back).
                if not idempotent and not isinstance(err, ClientConnectorError):
                    raise
                return await handler(self._session)

    def __create_message_id(self) -> str:
        """Create a unique hex message ID.

        The first 2 characters is the requestor_uuid (in hex),
        the next 4 characters are always the same for a session,
        and the last 10 characters are random."""
        return (
            f"{self._requestor_uuid.hex_value()}"
            f"{self._session_uuid}"
            f"{random.randint(0, 0xFFFFFFFF):010x}"
        ).lower()
