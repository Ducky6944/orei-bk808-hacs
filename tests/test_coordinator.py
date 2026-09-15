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


def test_num_ports():
    assert NUM_PORTS == 8


@pytest.mark.asyncio
async def test_port_status_read_api(hass):
    """input_is_on / output_is_on default to off and reflect the status arrays."""
    coord = OreiCoordinator(hass=hass, host="test.local")
    assert coord.input_is_on(1) is False
    assert coord.output_is_on(1) is False
    assert coord.input_is_on(99) is False

    # Simulate the parsed `get input status` / `get output status` arrays.
    coord._input_active = [True, False, False, False, False, False, False, False]
    coord._output_connect = [False, True, True, False, False, False, False, False]
    assert coord.input_is_on(1) is True
    assert coord.input_is_on(2) is False
    assert coord.output_is_on(2) is True
    assert coord.output_is_on(3) is True
    assert coord.output_is_on(1) is False
    await coord.shutdown()


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
