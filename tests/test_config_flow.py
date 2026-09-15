"""Tests for the Orei BK808 config flow."""

import pytest
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from custom_components.orei_bk808.const import DOMAIN, CONF_HOST

# `_validate` normalises whatever the sticky device returns into this shape.
SAMPLE = {
    "input_names": ["A", "B", "C", "D", "E", "F", "G", "H"],
    "output_names": [
        "Out A",
        "Out B",
        "Out C",
        "Out D",
        "Out E",
        "Out F",
        "Out G",
        "Out H",
    ],
}


@pytest.mark.asyncio
async def test_successful_setup_with_device_names(hass, enable_custom_integrations):
    """Happy path: accept host, then adopt the device's own port names."""

    async def _validate(host):
        assert host == "10.0.50.81"
        return SAMPLE

    with patch("custom_components.orei_bk808.config_flow._validate", new=_validate):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "10.0.50.81"}
        )
        # The flow pauses at the (pre-filled) naming step.
        assert result["type"] == "form"
        assert result["step_id"] == "naming"

        # Explicitly adopt the device-reported names and finish.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"use_device_names": True}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "10.0.50.81"
        assert result["data"]["host"] == "10.0.50.81"
        assert result["data"]["input_names"][0] == "A"
        assert result["data"]["output_names"][0] == "Out A"


@pytest.mark.asyncio
async def test_typed_names_are_respected(hass, enable_custom_integrations):
    """A user's typed names must win — not be silently overridden by device
    names (this is the regression that made naming take several attempts)."""

    async def _validate(host):
        return SAMPLE  # device *does* report names (previously clobbered typed ones)

    with patch("custom_components.orei_bk808.config_flow._validate", new=_validate):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "10.0.50.81"}
        )
        assert result["step_id"] == "naming"

        my_in = "My Input 1, My Input 2, I3, I4, I5, I6, I7, I8"
        my_out = "Living Room AVR, Bedroom TV, O3, O4, O5, O6, O7, O8"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"input_names": my_in, "output_names": my_out},
        )
        assert result["type"] == "create_entry"
        # _split_names strips whitespace, so compare against the stripped parts.
        assert result["data"]["input_names"] == [p.strip() for p in my_in.split(",")]
        assert result["data"]["output_names"] == [p.strip() for p in my_out.split(",")]


@pytest.mark.asyncio
async def test_connection_failed(hass, enable_custom_integrations):
    """Unreachable host surfaces a `cannot_connect` error."""
    import aiohttp

    async def _validate(host):
        raise aiohttp.ClientError("boom")

    with patch("custom_components.orei_bk808.config_flow._validate", new=_validate):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "10.0.50.81"}
        )
        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"
