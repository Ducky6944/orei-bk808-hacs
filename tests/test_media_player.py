"""Media player state derives from the matrix's live port status."""

import pytest

from custom_components.orei_bk808.coordinator import OreiCoordinator
from custom_components.orei_bk808.media_player import (
    _MediaInputPlayer,
    _MediaOutputPlayer,
)


@pytest.mark.asyncio
async def test_input_player_reports_on_or_off(hass):
    coord = OreiCoordinator(hass=hass, host="test.local")
    # Default: nothing powered -> off.
    in1 = _MediaInputPlayer(coord, 1, "test_local")
    assert in1.state == "off"
    assert in1.is_on is False

    # Source on input 1 powered -> on.
    coord._input_active = [True, False, False, False, False, False, False, False]
    assert in1.state == "on"
    assert in1.is_on is True

    # A different, un-powered input stays off.
    in6 = _MediaInputPlayer(coord, 6, "test_local")
    assert in6.state == "off"
    assert in6.is_on is False
    await coord.shutdown()


@pytest.mark.asyncio
async def test_output_player_reports_on_or_off(hass):
    coord = OreiCoordinator(hass=hass, host="test.local")
    out1 = _MediaOutputPlayer(coord, 1, "test_local")
    assert out1.state == "off"
    assert out1.is_on is False

    # Sinks on outputs 2 and 3 connected/on -> on.
    coord._output_connect = [False, True, True, False, False, False, False, False]
    assert out1.state == "off"  # output 1 not connected
    assert coord.output_is_on(2) is True
    out2 = _MediaOutputPlayer(coord, 2, "test_local")
    assert out2.state == "on"
    assert out2.is_on is True
    await coord.shutdown()
