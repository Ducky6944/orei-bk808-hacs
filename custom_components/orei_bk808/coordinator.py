"""Data coordinator for the Orei BK808 HDMI Matrix."""

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Literal, Optional

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_TIMEOUT,
    DEFAULT_INPUT_NAMES,
    DEFAULT_OUTPUT_NAMES,
    NUM_PORTS,
    CEC_INPUT_COMMANDS,
    CEC_OUTPUT_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)


class OreiCoordinator(DataUpdateCoordinator):
    """Poll the matrix via its JSON web API and expose command helpers."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        input_names: Optional[List[str]] = None,
        output_names: Optional[List[str]] = None,
    ) -> None:
        self.hass = hass
        self.host = host
        self._query_url = f"https://{host}/cgi-bin/query"
        self._instr_url = f"https://{host}/cgi-bin/instr"

        self._input_names = (
            list(input_names)[:NUM_PORTS]
            if input_names
            else list(DEFAULT_INPUT_NAMES[:NUM_PORTS])
        )
        self._output_names = (
            list(output_names)[:NUM_PORTS]
            if output_names
            else list(DEFAULT_OUTPUT_NAMES[:NUM_PORTS])
        )

        self._input_names += [""] * (NUM_PORTS - len(self._input_names))
        self._output_names += [""] * (NUM_PORTS - len(self._output_names))

        # Last-known state (device-reported, populated on each refresh)
        self._device_inputs: List[str] = [""] * NUM_PORTS
        self._device_outputs: List[str] = [""] * NUM_PORTS
        self._video_state: Dict[str, Any] = {}
        self._cec_state: Dict[str, Any] = {}

        self._session: Optional[aiohttp.ClientSession] = None

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=5),
        )

    # ------------------------------------------------------------------ session

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def shutdown(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------ helpers

    def input_display_name(self, input_num: int) -> str:
        if not (1 <= input_num <= NUM_PORTS):
            return f"Input {input_num}"
        i = input_num - 1
        return self._input_names[i] or self._device_inputs[i] or f"Input {input_num}"

    def output_display_name(self, output_num: int) -> str:
        if not (1 <= output_num <= NUM_PORTS):
            return f"Output {output_num}"
        o = output_num - 1
        return self._output_names[o] or self._device_outputs[o] or f"Output {output_num}"

    # ------------------------------------------------------------------ HTTP

    async def _http_get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP GET. State reads MUST return JSON, so an empty/non-JSON
        body here is a real failure and should be re-pollable."""
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        async with session.get(url, params=params, timeout=timeout, ssl=False) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise aiohttp.ClientResponseError(
                    resp.request_info, resp.history,
                    status=resp.status, message=f"HTTP {resp.status}: {body[:200]}",
                )
            try:
                return json.loads(body)
            except ValueError:
                raise aiohttp.ClientResponseError(
                    resp.request_info, resp.history,
                    status=resp.status,
                    message=f"Non-JSON response: {body[:200]!r}",
                )

    async def _http_post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """HTTP POST (command). The device sometimes returns an empty body
        on 200 when a request races its own state poller — we treat that as
        success since the command was accepted (HTTP 200)."""
        session = await self._get_session()
        timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        async with session.post(
            url, json=payload, timeout=timeout, headers=headers, ssl=False
        ) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise aiohttp.ClientResponseError(
                    resp.request_info, resp.history,
                    status=resp.status, message=f"HTTP {resp.status}: {body[:200]}",
                )
            if body and body != "\n":
                try:
                    return json.loads(body)
                except ValueError:
                    _LOGGER.warning(
                        "Command received non-JSON body: %r", body[:200]
                    )
            else:
                _LOGGER.debug("Command accepted (200, empty body)")
            return {}

    async def send_command(self, comhead: str, **fields: Any) -> Dict[str, Any]:
        """POST a command to /cgi-bin/instr and return the response body."""
        payload = {"comhead": comhead, "language": 0, **fields}
        _LOGGER.debug("Sending %s: %s", comhead, fields)
        try:
            result = await self._http_post(self._instr_url, payload)
            _LOGGER.debug("OK %s -> %s", comhead, result)
            return result
        except aiohttp.ClientError as err:
            _LOGGER.error("Communication error on %s from %s: %s", comhead, self.host, err)
            raise

    async def _query(self, comhead: str) -> Dict[str, Any]:
        """GET a state snapshot via /cgi-bin/query."""
        return await self._http_get(self._query_url, {"comhead": comhead})

    # ------------------------------------------------------------------ polling

    async def _async_update_data(self) -> Dict[str, Any]:
        # The device is single-connection and sticky about which state it
        # reports, so we poll sequentially until each of the two states
        # (video + cec) is seen at least once.
        last_error: Optional[BaseException] = None
        attempts = 6  # 2 states x up to 3 retries each
        got_video = self._video_state
        got_cec = self._cec_state

        for _ in range(attempts):
            if got_video and got_cec:
                break
            if not got_video:
                comhead = "get video status"
            else:
                comhead = "get cec status"
            try:
                body = await self._query(comhead)
            except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
                last_error = err
                continue
            body = body if isinstance(body, dict) else {}
            if "allsource" in body:
                got_video = body
            if "inputindex" in body or "outputindex" in body:
                got_cec = body

        if not got_video and not got_cec:
            raise UpdateFailed(
                f"All state queries failed for {self.host}: {last_error!r}"
            )

        self._video_state = got_video or {}
        self._cec_state = got_cec or {}

        if "allinputname" in self._video_state:
            self._device_inputs = list(self._video_state["allinputname"])[:NUM_PORTS]
        if "alloutputname" in self._video_state:
            self._device_outputs = list(self._video_state["alloutputname"])[:NUM_PORTS]

        # Fallback fill with configured names if device names empty
        self._device_inputs = [
            n or self._input_names[i] or f"Input {i+1}"
            for i, n in enumerate(self._device_inputs)
        ]
        self._device_outputs = [
            n or self._output_names[i] or f"Output {i+1}"
            for i, n in enumerate(self._device_outputs)
        ]

        return {
            "video": self._video_state,
            "cec": self._cec_state,
        }

    # ------------------------------------------------------------------ read API

    def get_power(self) -> Optional[bool]:
        if "power" in self._video_state:
            return bool(self._video_state["power"])
        if "power" in self._cec_state:
            return bool(self._cec_state["power"])
        return None

    def get_routed_input(self, output_num: int) -> Optional[int]:
        """Return the 1-indexed input routed to this output (or None/off)."""
        src = self._video_state.get("allsource", [])
        if not (1 <= output_num <= NUM_PORTS):
            return None
        val = src[output_num - 1] if output_num - 1 < len(src) else 0
        # 0 = off, >=9 = audio-output mapping, 1-8 = input
        try:
            ivalue = int(val)
        except (TypeError, ValueError):
            return None
        if ivalue == 0:
            return None
        if 1 <= ivalue <= 8:
            return ivalue
        return None

    # ------------------------------------------------------------------ actions

    async def set_route(self, output_num: int, input_num: int) -> None:
        """Route input_num to output_num. input_num of 8 = off (per UI convention)."""
        if not (1 <= output_num <= NUM_PORTS):
            raise ValueError(f"Invalid output {output_num}")
        if not (1 <= input_num <= NUM_PORTS + 1):
            raise ValueError(f"Invalid input {input_num}")
        await self.send_command("video switch", source=[output_num, input_num])
        await self.async_request_refresh()

    async def set_power(self, on: bool) -> None:
        await self.send_command("set poweronoff", power=1 if on else 0)
        await self.async_request_refresh()

    async def set_mute(self, output_num: int, muted: bool) -> None:
        if not (1 <= output_num <= NUM_PORTS):
            raise ValueError(f"Invalid output {output_num}")
        # Device convention: [output, 0|1]
        await self.send_command(
            "set output audio mute", mute=[output_num, 1 if muted else 0]
        )
        await self.async_request_refresh()

    async def set_cec_inputs(self, mask: List[int]) -> None:
        """Select which input ports are CEC-enabled (8-element mask)."""
        await self.send_command(
            "set cec index", inputindex=list(mask)[:NUM_PORTS], outputindex=[0] * NUM_PORTS
        )

    async def set_cec_outputs(self, mask: List[int]) -> None:
        """Select which output ports are CEC-enabled (8-element mask)."""
        await self.send_command(
            "set cec index", inputindex=[0] * NUM_PORTS, outputindex=list(mask)[:NUM_PORTS]
        )

    async def send_cec(
        self, side: Literal["input", "output"], port_num: int, command: str
    ) -> None:
        """Send a CEC command to a specific input or output port."""
        if not (1 <= port_num <= NUM_PORTS):
            raise ValueError(f"Invalid port {port_num}")

        table = CEC_INPUT_COMMANDS if side == "input" else CEC_OUTPUT_COMMANDS
        if command not in table:
            raise ValueError(f"Unknown CEC command '{command}' for {side} side")
        idx, _icon, _label = table[command]

        mask = [0] * NUM_PORTS
        mask[port_num - 1] = 1
        obj = 0 if side == "input" else 1

        await self.send_command(
            "cec command", object=obj, port=mask, index=idx
        )

    # Presets ------------------------------------------------------------------
    async def recall_preset(self, index: int) -> None:
        if not (1 <= index <= NUM_PORTS):
            raise ValueError(f"Preset index must be 1..{NUM_PORTS}")
        await self.send_command("preset set", index=index)
        await self.async_request_refresh()

    async def save_preset(self, index: int) -> None:
        if not (1 <= index <= NUM_PORTS):
            raise ValueError(f"Preset index must be 1..{NUM_PORTS}")
        await self.send_command("preset save", index=index)
        await self.async_request_refresh()

    async def clear_preset(self, index: int) -> None:
        if not (1 <= index <= NUM_PORTS):
            raise ValueError(f"Preset index must be 1..{NUM_PORTS}")
        await self.send_command("preset clear", index=index)

    async def set_preset_name(self, index: int, name: str) -> None:
        if not (1 <= index <= NUM_PORTS):
            raise ValueError(f"Preset index must be 1..{NUM_PORTS}")
        await self.send_command("preset name", index=index, name=name)
        await self.async_request_refresh()
