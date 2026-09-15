"""Pytest fixtures for Orei BK808 tests."""

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.config_entries import ConfigEntryState

from custom_components.orei_bk808.const import DOMAIN
from custom_components.orei_bk808.coordinator import OreiCoordinator


@pytest.fixture
def sample_video_status():
    """Sample `get video status` body (allsource is a flat list)."""
    return {
        "comhead": "get video status",
        "power": 1,
        "allsource": [5, 2, 1, 1, 1, 3, 1, 1],
        "allinputname": [
            "Unifi Protect",
            "Playstation 5",
            "Nintendo Switch",
            "Xbox Series X",
            "Gaming PC",
            "Apple TV",
            "Nvidia Shield",
            "Theater Zone 2",
        ],
        "alloutputname": [
            "Theater AVR",
            "Living Room AVR",
            "Main Bedroom Projector",
            "Kids Bedroom TV",
            "Guest Bedroom TV",
            "Living Room Balcony Amp",
            "Output7",
            "Output8",
        ],
        "allname": [
            "Preset1",
            "Preset2",
            "Preset3",
            "Preset4",
            "Preset5",
            "Preset6",
            "Preset7",
            "Preset8",
        ],
        "version": "V1.10.01",
    }


@pytest.fixture
def sample_cec_status():
    """Sample `get cec status` body."""
    return {
        "comhead": "get cec status",
        "power": 1,
        "allinputname": [
            "In A",
            "In B",
            "In C",
            "In D",
            "In E",
            "In F",
            "In G",
            "In H",
        ],
        "alloutputname": [
            "Out A",
            "Out B",
            "Out C",
            "Out D",
            "Out E",
            "Out F",
            "Out G",
            "Out H",
        ],
        "inputindex": [1, 0, 0, 0, 0, 0, 0, 0],
        "outputindex": [1, 0, 0, 0, 0, 0, 0, 0],
    }


@pytest.fixture
def mock_coordinator(hass: HomeAssistant):
    """A coordinator not tied to a live device."""
    return OreiCoordinator(
        hass=hass,
        host="test.local",
        input_names=["Test 1", "Test 2"],
        output_names=["Test Out 1", "Test Out 2"],
    )


@pytest.fixture
async def initialized_integration(
    hass: HomeAssistant, sample_video_status, sample_cec_status
):
    """Set up a fully initialized integration with mocked HTTP."""

    def _get(url, params=None, **kwargs):
        resp = AsyncMock()
        resp.status = 200
        return resp

    async def _get_cm(head):
        if "video" in head:
            return sample_video_status
        return sample_cec_status

    with patch(
        "custom_components.orei_bk808.coordinator.OreiCoordinator._async_update_data",
        new=lambda self: _make_update(self, sample_video_status, sample_cec_status),
    ), patch(
        "custom_components.orei_bk808.coordinator.OreiCoordinator._query",
        new=lambda self, comhead: _make_query(
            self, comhead, sample_video_status, sample_cec_status
        ),
    ):
        from homeassistant.config_entries import ConfigEntry

        entry = ConfigEntry(
            version=1,
            domain=DOMAIN,
            title="test.local",
            data={
                "host": "test.local",
                "input_names": [
                    "PS5",
                    "Xbox",
                    "PC",
                    "Apple TV",
                    "Shield",
                    "Cameras",
                    "Zone 2",
                    "Backup",
                ],
                "output_names": [
                    "Living Room",
                    "Bedroom",
                    "Projector",
                    "Kitchen",
                    "Guest",
                    "Balcony",
                    "Out 7",
                    "Out 8",
                ],
            },
            source="user",
            entry_id="test_entry_1",
        )
        entry.add_to_hass(hass)
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state == ConfigEntryState.LOADED
        yield entry
        await hass.config_entries.async_remove(entry.entry_id)


def _make_update(self, video, cec):
    async def _update():
        self._video_state = video
        self._cec_state = cec
        if "allinputname" in video:
            self._device_inputs = list(video["allinputname"])[:8]
        if "alloutputname" in video:
            self._device_outputs = list(video["alloutputname"])[:8]
        return {"video": video, "cec": cec}

    return _update()


def _make_query(self, comhead, video, cec):
    async def _query():
        if "video" in comhead:
            self._video_state = video
            return video
        self._cec_state = cec
        return cec

    return _query()
