"""Data coordinator for the Orei BK808 HDMI Matrix."""

import asyncio
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
    ROUTE_SETTLE_DELAY,
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
        # Per-port live status: input source power (`inactive`: 1=on) and
        # output sink connection (`allconnect`: 1=on). Backs media_player state.
        self._input_active: List[bool] = [False] * NUM_PORTS
        self._output_connect: List[bool] = [False] * NUM_PORTS
        self._last_error: Optional[BaseException] = None

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
        return (
            self._output_names[o] or self._device_outputs[o] or f"Output {output_num}"
        )

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
                    resp.request_info,
                    resp.history,
                    status=resp.status,
                    message=f"HTTP {resp.status}: {body[:200]}",
                )
            try:
                return json.loads(body)
            except ValueError:
                raise aiohttp.ClientResponseError(
                    resp.request_info,
                    resp.history,
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
                    resp.request_info,
                    resp.history,
                    status=resp.status,
                    message=f"HTTP {resp.status}: {body[:200]}",
                )
            if body and body != "\n":
                try:
                    return json.loads(body)
                except ValueError:
                    _LOGGER.warning("Command received non-JSON body: %r", body[:200])
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
            _LOGGER.error(
                "Communication error on %s from %s: %s", comhead, self.host, err
            )
            raise

    async def _query(self, comhead: str) -> Dict[str, Any]:
        """GET a state snapshot via /cgi-bin/query."""
        return await self._http_get(self._query_url, {"comhead": comhead})

    # ------------------------------------------------------------------ polling

    async def _fetch_states(self) -> bool:
        """Hit the device for fresh routing state.

        The only thing we actually *consume* from the device is the routing
        blob (`allsource`, plus the port names and power it carries). The
        device is single-connection and sticky: it latches the payload it
        returns regardless of which `comhead` we ask for, and that payload
        sometimes is the video/preset blob and sometimes an `input status`
        blob. So we poll until we capture a body that carries `allsource`,
        treating that as success.

        Returns True if a usable routing blob was read this round.
        """
        last_error: Optional[BaseException] = None
        attempts = 6  # up to 6 tries until the routing blob shows up
        fresh_video: Optional[Dict[str, Any]] = None
        fresh_cec: Optional[Dict[str, Any]] = None

        for _ in range(attempts):
            if fresh_video is not None:
                break
            try:
                body = await self._query("get video status")
            except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
                last_error = err
                continue
            body = body if isinstance(body, dict) else {}
            if "allsource" in body:
                fresh_video = body
            # Capture cec-style payload opportunistically (secondary power
            # fallback only — never required for success).
            if fresh_cec is None and ("inputindex" in body or "outputindex" in body):
                fresh_cec = body

        # Only replace cached state with what we actually read this round.
        if fresh_video is not None:
            self._video_state = fresh_video
        if fresh_cec is not None:
            self._cec_state = fresh_cec
        self._last_error = last_error
        return fresh_video is not None

    async def _fetch_port_status(self) -> None:
        """Read per-port live status (input power + output sink connection).

        These arrive as `get input status` / `get output status` POST bodies
        and are separate from the sticky routing blob. A single transient
        failure here must NOT fail the whole refresh — the state is just
        stale until the next poll (same leniency as the CEC payload capture).
        """
        # input  -> `inactive`: 1 = source powered/on, 0 = off
        try:
            body = await self.send_command("get input status")
            if isinstance(body, dict) and "inactive" in body:
                vals = list(body["inactive"])[:NUM_PORTS]
                vals += [0] * (NUM_PORTS - len(vals))
                self._input_active = [bool(v) for v in vals]
        except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
            _LOGGER.debug("get input status failed (%r); keeping last-known", err)

        # output -> `allconnect`: 1 = sink connected/on, 0 = off
        try:
            body = await self.send_command("get output status")
            if isinstance(body, dict) and "allconnect" in body:
                vals = list(body["allconnect"])[:NUM_PORTS]
                vals += [0] * (NUM_PORTS - len(vals))
                self._output_connect = [bool(v) for v in vals]
        except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
            _LOGGER.debug("get output status failed (%r); keeping last-known", err)

    async def _async_update_data(self) -> Dict[str, Any]:
        video_ok = await self._fetch_states()
        await self._fetch_port_status()

        # First-ever poll with no usable state is a real outage.
        if not video_ok and not self._video_state and not self._cec_state:
            raise UpdateFailed(
                f"All state queries failed for {self.host}: {self._last_error!r}"
            )
        # Subsequent polls: keep last-known-good rather than flapping entities
        # on a transient blip or an odd single-connection response.
        if not video_ok:
            _LOGGER.debug(
                "Refresh %s failed (%r); keeping last-known state",
                self.host,
                self._last_error,
            )

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

    def input_is_on(self, input_num: int) -> bool:
        """True if the *source* on this input is powered/on (`inactive`=1)."""
        if 1 <= input_num <= NUM_PORTS:
            return bool(self._input_active[input_num - 1])
        return False

    def output_is_on(self, output_num: int) -> bool:
        """True if the *sink* on this output is connected/on (`allconnect`=1)."""
        if 1 <= output_num <= NUM_PORTS:
            return bool(self._output_connect[output_num - 1])
        return False

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

    def _apply_route(self, output_num: int, input_num: int) -> None:
        """Optimistically reflect a route in the local state so entities
        update immediately, before the device confirms."""
        src = self._video_state.get("allsource")
        if not isinstance(src, list):
            src = [0] * NUM_PORTS
        while len(src) < NUM_PORTS:
            src.append(0)
        src[output_num - 1] = input_num
        self._video_state["allsource"] = src

    async def set_route(self, output_num: int, input_num: int) -> None:
        """Route input_num to output_num. input_num of 0 = off."""
        if not (1 <= output_num <= NUM_PORTS):
            raise ValueError(f"Invalid output {output_num}")
        if not (0 <= input_num <= NUM_PORTS):
            raise ValueError(f"Invalid input {input_num}")
        await self.send_command("video switch", source=[output_num, input_num])

        # Make the UI reflect the new route right away (the device is the
        # source of truth, but it lags a beat in reporting the change).
        self._apply_route(output_num, input_num)
        self.async_update_listeners()

        # Give the matrix a moment to register the switch, then confirm
        # against the real state so any discrepancy self-corrects.
        await asyncio.sleep(ROUTE_SETTLE_DELAY)
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
            "set cec index",
            inputindex=list(mask)[:NUM_PORTS],
            outputindex=[0] * NUM_PORTS,
        )

    async def set_cec_outputs(self, mask: List[int]) -> None:
        """Select which output ports are CEC-enabled (8-element mask)."""
        await self.send_command(
            "set cec index",
            inputindex=[0] * NUM_PORTS,
            outputindex=list(mask)[:NUM_PORTS],
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

        await self.send_command("cec command", object=obj, port=mask, index=idx)

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
