"""Tests for Orei BK808 config flow."""

import pytest
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.setup import async_setup_component
from custom_components.orei_bk808.const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD

@pytest.mark.asyncio
async def test_successful_setup(hass, mock_aioresponse):
    """Test successful config flow setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER}
    )
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.50.81",
            CONF_USERNAME: "Admin",
            CONF_PASSWORD: "admin"
        }
    )
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "naming"
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={}
    )
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "10.0.50.81"

@pytest.mark.asyncio
async def test_connection_failed(hass, mock_aioresponse):
    """Test failed connection during setup."""
    mock_aioresponse.return_value.status = 401
    
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER}
    )
    
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.50.81",
            CONF_USERNAME: "Admin",
            CONF_PASSWORD: "wrongpassword"
        }
    )
    
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "cannot_connect"
