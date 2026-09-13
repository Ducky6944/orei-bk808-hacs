"""Data coordinator for Orei BK808 Matrix."""

import logging
import base64
from datetime import timedelta
from typing import Any, Dict, Optional
import aiohttp
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, DEFAULT_TIMEOUT, CEC_OPCODES, INPUT_CEC_GROUPS,
    OUTPUT_CEC_GROUPS, QUICK_ACTIONS, DEFAULT_INPUT_NAMES,
    DEFAULT_OUTPUT_NAMES
)

_LOGGER = logging.getLogger(__name__)

class OreiCoordinator(DataUpdateCoordinator):
    """Data coordinator for Orei BK808."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        input_names: list | None = None,
        output_names: list | None = None
    ):
        """Initialize the coordinator."""
        self.hass = hass
        self.host = host
        self.base_url = f"https://{host}/cgi-bin/instr"
        self.auth = f"{username}:{password}"
        
        self.input_names = input_names or DEFAULT_INPUT_NAMES.copy()
        self.output_names = output_names or DEFAULT_OUTPUT_NAMES.copy()
        
        self.input_names.extend([""] * (8 - len(self.input_names)))
        self.output_names.extend([""] * (8 - len(self.output_names)))
        
        self.inputs = {i+1: name for i, name in enumerate(self.input_names[:8])}
        self.outputs = {i+1: name for i, name in enumerate(self.output_names[:8])}
        
        self._video_status: Dict[str, Any] = {}
        self._last_error: Optional[str] = None
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
    
    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the matrix."""
        try:
            await self.get_video_status()
            return self._video_status
        except UpdateFailed as err:
            raise err
        except Exception as err:
            self._last_error = str(err)
            raise UpdateFailed(f"Update failed: {err}") from err
    
    async def send_command(self, comhead: str, **kwargs) -> dict:
        """Send a command to the matrix via HTTP API."""
        payload = {"comhead": comhead, "language": 0, **kwargs}
        
        auth_header = base64.b64encode(self.auth.encode()).decode()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=DEFAULT_TIMEOUT,
                    ssl=False,
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("result", result)
                    else:
                        error_text = await resp.text()
                        raise aiohttp.ClientError(f"HTTP {resp.status}: {error_text}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Communication error with %s: %s", self.host, e)
            raise
    
    async def get_video_status(self) -> Dict[str, Any]:
        """Get current video routing status."""
        result = await self.send_command("get video status")
        self._video_status = result.get("result", {})
        return self._video_status
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status."""
        result = await self.send_command("get system status")
        return result.get("result", {})
    
    async def route_video(self, input_num: int, output_num: int) -> dict:
        """Route specific input to output."""
        if not (1 <= input_num <= 8) or not (1 <= output_num <= 8):
            raise ValueError("Input and output must be between 1 and 8")
        return await self.send_command("video switch", source=[input_num, output_num])
    
    async def route_all(self, routes: list[list[int]]) -> dict:
        """Route multiple inputs in one call."""
        return await self.send_command("video switch", source=routes)
    
    async def power_matrix(self, on: bool) -> dict:
        """Turn matrix power on/off."""
        return await self.send_command("set poweronoff", power=1 if on else 0)
    
    async def save_preset(self, index: int) -> dict:
        """Save current routing to preset slot."""
        if not (1 <= index <= 8):
            raise ValueError("Preset index must be between 1 and 8")
        return await self.send_command("preset save", index=index)
    
    async def recall_preset(self, index: int) -> dict:
        """Recall routing from preset slot."""
        if not (1 <= index <= 8):
            raise ValueError("Preset index must be between 1 and 8")
        return await self.send_command("preset set", index=index)
    
    async def send_cec_command(
        self,
        target_type: str,
        port_num: int,
        cec_command: str
    ) -> dict:
        """Send CEC command to input or output."""
        if not (1 <= port_num <= 8):
            raise ValueError("Port number must be between 1 and 8")
        
        if cec_command not in CEC_OPCODES:
            _LOGGER.warning("Unknown CEC command: %s", cec_command)
        
        port_array = [0] * 8
        port_array[port_num - 1] = 1
        
        index = CEC_OPCODES.get(cec_command, 0)
        
        return await self.send_command(
            "cec command",
            object=0 if target_type == "input" else 1,
            port=port_array,
            index=index
        )
    
    async def send_input_cec(self, input_num: int, command: str) -> dict:
        """Send CEC command to input device."""
        return await self.send_cec_command("input", input_num, command)
    
    async def send_output_cec(self, output_num: int, command: str) -> dict:
        """Send CEC command to output device."""
        return await self.send_cec_command("output", output_num, command)
    
    async def execute_quick_action(self, action_name: str, target: str = None) -> None:
        """Execute predefined quick action macro."""
        actions = QUICK_ACTIONS.get(action_name, [])
        
        for action, tgt in actions:
            try:
                if action == "power_on" and tgt == "All outputs":
                    await self.power_matrix(True)
                elif action == "standby" and tgt == "All outputs":
                    await self.power_matrix(False)
                elif action.startswith("input_") and action.endswith("_to_output_"):
                    parts = action.split("_to_output_")
                    inp = int(parts[0].split("_")[1])
                    out = int(parts[1])
                    await self.route_video(inp, out)
                elif action.startswith("input_") and "_to_all_outputs" in action:
                    inp = int(action.split("_")[1])
                    for out in range(1, 9):
                        await self.route_video(inp, out)
                        await asyncio.sleep(0.1)
            except Exception as e:
                _LOGGER.warning("Quick action failed: %s", e)
    
    def get_input_display_name(self, input_num: int) -> str:
        """Get display name for input."""
        return self.inputs.get(input_num, f"Input {input_num}") or f"Input {input_num}"
    
    def get_output_display_name(self, output_num: int) -> str:
        """Get display name for output."""
        return self.outputs.get(output_num, f"Output {output_num}") or f"Output {output_num}"
    
    def get_routing_for_output(self, output_num: int) -> tuple[int, str] | None:
        """Get current routing for a specific output."""
        if not self._video_status:
            return None
        
        allsource = self._video_status.get("allsource", [])
        for mapping in allsource:
            if len(mapping) >= 2 and mapping[1] == output_num:
                input_num = mapping[0]
                input_name = self.get_input_display_name(input_num)
                return (input_num, input_name)
        return None
