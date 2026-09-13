"""Pytest fixtures for Orei BK808 tests."""

import pytest
import pytest_homeassistant_custom_component
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.config_entries import ConfigEntryState
import aiohttp

from custom_components.orei_bk808.const import DOMAIN
from custom_components.orei_bk808.coordinator import OreiCoordinator

@pytest.fixture
def mock_aioresponse():
    """Mock aiohttp responses."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "result": {
                "power": 1,
                "allsource": [[1, 1], [2, 2]],
                "allinputname": ["Input 1", "Input 2"],
                "alloutputname": ["Output 1", "Output 2"],
                "version": "1.0.5"
            }
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_post.return_value = mock_response
        
        yield mock_post

@pytest.fixture
def mock_coordinator(hass: HomeAssistant):
    """Create a mock coordinator."""
    coordinator = OreiCoordinator(
        hass=hass,
        host="test.local",
        username="test_user",
        password="test_pass",
        input_names=["Test 1", "Test 2"],
        output_names=["Test Out 1", "Test Out 2"]
    )
    return coordinator

@pytest.fixture
async def initialized_integration(hass: HomeAssistant, mock_aioresponse):
    """Set up a fully initialized integration."""
    from homeassistant.config_entries import ConfigEntry
    
    config_entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="test.local",
        data={
            "host": "test.local",
            "username": "test_user",
            "password": "test_pass",
            "input_names": ["PS5", "Xbox", "PC", "Appletv", "Shield", "Cameras", "Zone2", "Backup"],
            "output_names": ["LivingRoom", "Bedroom", "Projector", "Kitchen", "Guest", "Balcony", "Out7", "Out8"]
        },
        source="user",
        entry_id="test_entry_1",
    )
    
    config_entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    
    assert config_entry.state == ConfigEntryState.LOADED
    
    yield config_entry
    
    await hass.config_entries.async_remove(config_entry.entry_id)

@pytest.fixture
def sample_video_status():
    """Sample video status response."""
    return {
        "power": 1,
        "allsource": [
            [1, 1], [2, 2], [1, 3], [1, 4],
            [1, 5], [1, 6], [1, 7], [1, 8]
        ],
        "allinputname": ["Unifi Protect", "PS5", "Nintendo", "Xbox", "PC", "Apple TV", "Shield", "Zone2"],
        "alloutputname": ["AVR", "LR AVR", "Bedroom", "Kids", "Guest", "Balcony", "Out7", "Out8"],
        "version": "1.0.5"
    }
