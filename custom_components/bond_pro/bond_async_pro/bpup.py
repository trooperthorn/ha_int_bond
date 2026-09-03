"""Bond BPUP (Bond Push UDP Protocol) wrapper with automatic reconnect."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional, cast

import orjson

BPUP_INIT_PUSH_MESSAGE = b"\n"
BPUP_PORT = 30007
BPUP_ALIVE_TIMEOUT = 70
# Half the bridge's 60s session timeout; see docs/protocol.md.
BPUP_KEEP_ALIVE_INTERVAL = 30
RECONNECT_MIN_DELAY = 1.0
RECONNECT_MAX_DELAY = 60.0

_LOGGER = logging.getLogger(__name__)


class BPUPSubscriptions:
    """Store BPUP subscriptions."""

    def __init__(self) -> None:
        """Init and store callbacks."""
        self._callbacks: Dict[str, List[Callable]] = {}
        self.last_message_time: float = -BPUP_ALIVE_TIMEOUT

    @property
    def alive(self) -> bool:
        """Return if the subscriptions are considered alive."""
        return (time.monotonic() - self.last_message_time) < BPUP_ALIVE_TIMEOUT

    def connection_lost(self) -> None:
        """Set the last message time to never."""
        self.last_message_time = -BPUP_ALIVE_TIMEOUT

    def subscribe(self, device_id: str, callback: Callable) -> None:
        """Subscribe to BPUP updates."""
        self._callbacks.setdefault(device_id, []).append(callback)

    def unsubscribe(self, device_id: str, callback: Callable) -> None:
        """Unsubscribe from BPUP updates."""
        self._callbacks[device_id].remove(callback)

    def notify(self, json_msg: Dict[str, Any]) -> None:
        """Notify subscribers of an update."""
        self.last_message_time = time.monotonic()

        if json_msg.get("s", 200) != 200:
            _LOGGER.debug("BPUP error frame: %s", json_msg)
            return

        topic = json_msg.get("t")
        if not topic:
            # Keep-alive acknowledgements carry no topic.
            return

        parts = topic.split("/")
        if len(parts) < 2:
            _LOGGER.debug("BPUP frame with unexpected topic: %s", json_msg)
            return
        device_id = parts[1]

        for callback in self._callbacks.get(device_id, []):
            callback(json_msg)


class BPUProtocol(asyncio.Protocol):
    """Implements BPUP Protocol."""

    def __init__(
        self,
        bpup_subscriptions: BPUPSubscriptions,
        on_connection_lost: Optional[Callable[[], None]] = None,
    ) -> None:
        """Create BPUP Protocol."""
        self.loop = asyncio.get_event_loop()
        self.bpup_subscriptions = bpup_subscriptions
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.keep_alive: Optional[asyncio.TimerHandle] = None
        self._on_connection_lost = on_connection_lost

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Connect or reconnect to the device."""
        self.transport = cast(asyncio.DatagramTransport, transport)
        if self.keep_alive:
            self.keep_alive.cancel()
            self.keep_alive = None
        self.send_keep_alive()

    def send_keep_alive(self) -> None:
        """Send a keep alive every BPUP_KEEP_ALIVE_INTERVAL seconds."""
        if not self.transport or self.transport.is_closing():
            return
        self.transport.sendto(BPUP_INIT_PUSH_MESSAGE)
        self.keep_alive = self.loop.call_later(
            BPUP_KEEP_ALIVE_INTERVAL, self.send_keep_alive
        )

    def datagram_received(self, data: bytes, addr: Any) -> None:
        """Process incoming state changes."""
        _LOGGER.debug("%s: BPUP message: %s", addr, data)
        try:
            self.bpup_subscriptions.notify(orjson.loads(data.decode().rstrip("\n")))
        except orjson.JSONDecodeError as ex:
            _LOGGER.warning(
                "%s: Failed to process BPUP message: %s: %s", addr, data, ex
            )

    def error_received(self, exc: Optional[Exception]) -> None:
        """Log errors."""
        _LOGGER.debug("BPUP error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Handle connection lost: notify owner so it can reconnect."""
        self.bpup_subscriptions.connection_lost()
        if self.keep_alive:
            self.keep_alive.cancel()
            self.keep_alive = None
        if exc:
            _LOGGER.debug("BPUP connection lost: %s", exc)
        if self._on_connection_lost:
            self._on_connection_lost()

    def stop(self) -> None:
        """Stop the client."""
        _LOGGER.debug("BPUP connection stopping: %s", self.transport)
        self._on_connection_lost = None
        self.bpup_subscriptions.connection_lost()
        if self.keep_alive:
            self.keep_alive.cancel()
            self.keep_alive = None
        if self.transport:
            self.transport.close()


class BPUPClient:
    """Owns a BPUP endpoint and transparently reconnects it.

    The upstream implementation created the datagram endpoint once; if the
    socket errored (bridge reboot, network blip, interface change) push
    updates were gone forever and consumers fell back to slow polling.  This
    client watches for connection loss and message staleness and rebuilds the
    endpoint with jittered exponential backoff.
    """

    def __init__(self, host: str, subscriptions: BPUPSubscriptions) -> None:
        """Initialize the client for a host."""
        self._host = host
        self._subscriptions = subscriptions
        self._protocol: Optional[BPUProtocol] = None
        self._watchdog: Optional[asyncio.TimerHandle] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stopped = False
        self._delay = RECONNECT_MIN_DELAY
        self._loop = asyncio.get_event_loop()

    async def start(self) -> None:
        """Create the initial endpoint."""
        await self._connect()
        self._schedule_watchdog()

    async def _connect(self) -> None:
        _, protocol = await self._loop.create_datagram_endpoint(
            lambda: BPUProtocol(self._subscriptions, self._on_connection_lost),
            remote_addr=(self._host, BPUP_PORT),
        )
        self._protocol = cast(BPUProtocol, protocol)

    def _on_connection_lost(self) -> None:
        if self._stopped:
            return
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._stopped or (self._reconnect_task and not self._reconnect_task.done()):
            return
        delay = self._delay + random.uniform(0, self._delay / 2)
        self._delay = min(self._delay * 2, RECONNECT_MAX_DELAY)
        _LOGGER.debug("BPUP reconnecting to %s in %.1fs", self._host, delay)
        self._reconnect_task = self._loop.create_task(self._reconnect(delay))

    async def _reconnect(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._stopped:
            return
        try:
            await self._connect()
        except OSError as ex:
            _LOGGER.debug("BPUP reconnect to %s failed: %s", self._host, ex)
            self._schedule_reconnect()

    def _schedule_watchdog(self) -> None:
        if self._stopped:
            return
        self._watchdog = self._loop.call_later(BPUP_ALIVE_TIMEOUT, self._check_alive)

    def _check_alive(self) -> None:
        """Rebuild the endpoint if no message arrived within the timeout."""
        if self._stopped:
            return
        if not self._subscriptions.alive:
            self._delay = RECONNECT_MIN_DELAY
            if self._protocol:
                # Closing triggers connection_lost -> reconnect.
                protocol, self._protocol = self._protocol, None
                protocol.stop()
                self._schedule_reconnect()
        self._schedule_watchdog()

    def stop(self) -> None:
        """Stop the client permanently."""
        self._stopped = True
        if self._watchdog:
            self._watchdog.cancel()
            self._watchdog = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._protocol:
            self._protocol.stop()
            self._protocol = None


async def start_bpup(
    host_ip_addr: str, bpup_subscriptions: BPUPSubscriptions
) -> Callable:
    """Create the socket and protocol; returns a stop callable.

    Kept signature-compatible with upstream bond-async, but now backed by a
    reconnecting client.
    """
    client = BPUPClient(host_ip_addr, bpup_subscriptions)
    await client.start()
    return client.stop
