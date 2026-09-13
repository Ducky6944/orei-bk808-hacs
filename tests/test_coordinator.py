"""Tests for OreiCoordinator."""

import pytest
from unittest.mock import AsyncMock
from custom_components.orei_bk808.coordinator import OreiCoordinator
from custom_components.orei_bk808.const import CEC_OPCODES

@pytest.mark.asyncio
async def test_coordinator_initialization(mock_coordinator, sample_video_status):
    """Test coordinator initializes correctly."""
    assert mock_coordinator.host == "test.local"
    assert "Test 1" in mock_coordinator.input_names
    assert "Test Out 1" in mock_coordinator.output_names
    
    assert mock_coordinator.inputs[1]
