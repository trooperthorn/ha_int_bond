"""Shared fixtures for Bond Pro tests.

pytest-homeassistant-custom-component provides the `hass` and
`enable_custom_integrations` fixtures. The repo root is put on sys.path so
`custom_components.bond_pro` imports resolve when pytest runs from anywhere.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

import pytest
import pytest_socket

if sys.platform == "win32":
    # aiodns (used by HA's shared aiohttp session) requires a selector
    # event loop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


# pytest-homeassistant-custom-component calls pytest_socket.disable_socket()
# before every test, which blocks creation of every non-unix socket.  Linux
# asyncio builds its self-pipe from an AF_UNIX socketpair, but Windows has no
# AF_UNIX -- the event loop itself needs an AF_INET loopback pair, so no
# `hass` test can even start.  Replace disable_socket with a loopback-only
# connect restriction, which is the same isolation level Linux ends up with.
if sys.platform == "win32":

    def _disable_socket_loopback_ok(allow_unix_socket: bool = False) -> None:
        pytest_socket.enable_socket()
        pytest_socket.socket_allow_hosts(
            ["127.0.0.1", "::1"], allow_unix_socket=True
        )

    pytest_socket.disable_socket = _disable_socket_loopback_ok


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield
