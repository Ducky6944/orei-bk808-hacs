"""Tests for the Orei BK808 config flow."""

import pytest
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER
from custom_components.orei_bk808.const import DOMAIN, CONF_HOST

SAMPLE = {
    "comhead": "get cec status",
    "power": 1,
    "allinputname": ["A", "B", "C", "D", "E", "F", "G", "H"],
    "alloutputname": ["Out A", "Out B", "Out C", "Out D", "Out E", "Out F", "Out G", "Out H"],
    "inputindex": [1, 0, 0, 0, 0, 0, 0, 0],
    "outputindex": [1, 0, 0, 0, 0, 0, 0, 0],
}


@pytest.mark.asyncio
async def test_successful_setup(hass):
    """Happy path: show form, accept host, create entry."""

    async def _validate(host):
        assert host == "192.168.1.100"
        return SAMPLE

    with patch(
        "custom_components.orei_bk808.config_flow._validate", new=_validate
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "192.168.1.100"
        assert result["data"]["host"] == "192.168.1.100"
        assert result["data"]["input_names"][0] == "A"
        assert result["data"]["output_names"][0] == "Out A"


@pytest.mark.asyncio
async def test_connection_failed(hass):
    """Unreachable host surfaces a `cannot_connect` error."""
    import aiohttp

    async def _validate(host):
        raise aiohttp.ClientError("boom")

    with patch(
        "custom_components.orei_bk808.config_flow._validate", new=_validate
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"]["base"] == "cannot_connect"
