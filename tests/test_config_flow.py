"""Tests for the Bond Pro config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bond_pro.const import DOMAIN

from .common import (
    BOND_ID,
    HOST,
    TOKEN,
    make_client_response_error,
    make_entry,
    patch_bond_api,
    patch_start_bpup,
)


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Full happy-path user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch_bond_api(), patch_start_bpup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_ACCESS_TOKEN: TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Master BRIDGE"
    assert result["data"] == {CONF_HOST: HOST, CONF_ACCESS_TOKEN: TOKEN}
    assert result["result"].unique_id == BOND_ID


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """A 401 during validation shows invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch_bond_api(version_side_effect=make_client_response_error(401)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_ACCESS_TOKEN: "bad"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """A connection error during validation shows cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch_bond_api(version_side_effect=ClientConnectionError()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: HOST, CONF_ACCESS_TOKEN: TOKEN},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_updates_token(hass: HomeAssistant) -> None:
    """The reauth flow validates and stores a new token."""
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=dict(entry.data),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch_bond_api(), patch_start_bpup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-token"


async def test_reconfigure_flow_updates_host(hass: HomeAssistant) -> None:
    """The reconfigure flow validates and stores a new host."""
    entry = make_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch_bond_api(), patch_start_bpup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.99", CONF_ACCESS_TOKEN: TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.99"


async def test_discovery_confirm_with_fetched_token(hass: HomeAssistant) -> None:
    """Zeroconf discovery auto-fetches the token when unlocked."""
    from types import SimpleNamespace

    # The flow handler only reads .name and .host; a namespace avoids
    # importing the zeroconf package, which this venv does not carry.
    discovery_info = SimpleNamespace(
        name=f"{BOND_ID}.some-other-tail-info",
        host=HOST,
    )

    with (
        patch_bond_api(),
        patch_start_bpup(),
        patch(
            "custom_components.bond_pro.config_flow.async_get_token",
            AsyncMock(return_value=TOKEN),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == TOKEN
