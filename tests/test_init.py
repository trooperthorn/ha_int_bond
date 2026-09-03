"""Tests for Bond Pro setup and unload."""

from __future__ import annotations

from aiohttp import ClientConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.bond_pro.const import DOMAIN

from .common import (
    BOND_ID,
    make_client_response_error,
    make_entry,
    patch_bond_api,
    patch_start_bpup,
    setup_bond,
)


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """Successful setup registers the hub device and unload cleans up."""
    entry = await setup_bond(hass)
    assert entry.state is ConfigEntryState.LOADED

    registry = dr.async_get(hass)
    hub_device = registry.async_get_device_by_identifier(
        (DOMAIN, BOND_ID), entry.entry_id
    )
    assert hub_device is not None
    assert hub_device.manufacturer == "Olibra"
    assert hub_device.sw_version == "v4.32.7"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_invalid_token_starts_reauth(hass: HomeAssistant) -> None:
    """A 401 during setup puts the entry in SETUP_ERROR and starts reauth."""
    entry = make_entry()
    entry.add_to_hass(hass)
    with (
        patch_bond_api(version_side_effect=make_client_response_error(401)),
        patch_start_bpup(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_setup_offline_retries(hass: HomeAssistant) -> None:
    """A connection error during setup leads to SETUP_RETRY."""
    entry = make_entry()
    entry.add_to_hass(hass)
    with (
        patch_bond_api(version_side_effect=ClientConnectionError()),
        patch_start_bpup(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
