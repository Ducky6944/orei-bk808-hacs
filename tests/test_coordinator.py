"""Basic sanity tests for the coordinator and CEC command tables."""

import pytest

from custom_components.orei_bk808.const import (
    CEC_INPUT_COMMANDS,
    CEC_OUTPUT_COMMANDS,
    NUM_PORTS,
)
from custom_components.orei_bk808.coordinator import OreiCoordinator


def test_cec_input_commands_have_icons():
    for name, (idx, icon, label) in CEC_INPUT_COMMANDS.items():
        assert isinstance(idx, int)
        assert isinstance(icon, str)
        assert isinstance(label, str) and label


def test_cec_output_commands_have_icons():
    for name, (idx, icon, label) in CEC_OUTPUT_COMMANDS.items():
        assert isinstance(idx, int)
        assert isinstance(icon, str)
        assert isinstance(label, str) and label


@pytest.mark.asyncio
async def test_coordinator_initialization(hass):
    coord = OreiCoordinator(
        hass=hass,
        host="test.local",
        input_names=["Test 1"],
        output_names=["Test Out 1"],
    )
    assert coord.host == "test.local"
    assert coord.input_display_name(1) == "Test 1"
    assert coord.input_display_name(2) == "Input 2"
    assert coord.output_display_name(1) == "Test Out 1"
    assert coord.get_routed_input(1) is None
    await coord.shutdown()
