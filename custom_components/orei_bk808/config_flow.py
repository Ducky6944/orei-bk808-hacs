"""Config flow for the Orei BK808 HDMI Matrix."""

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_OUTPUT_NAMES,
    DEFAULT_INPUT_NAMES,
    DEFAULT_OUTPUT_NAMES,
    DEFAULT_TIMEOUT,
    NUM_PORTS,
)

_LOGGER = logging.getLogger(__name__)


def _split_names(raw: str) -> list[str]:
    """Split a comma-separated string into up to 8 non-empty names."""
    names = [p.strip() for p in raw.split(",") if p.strip()]
    return names[:NUM_PORTS]


def _names_to_display(names: Any) -> str:
    """Render a names field for display (join list, or return string)."""
    if isinstance(names, (list, tuple)):
        return ",".join(str(n) for n in names if str(n).strip())
    return str(names or "")


def _pad_names(names: list[str]) -> list[str]:
    """Pad a names list up to NUM_PORTS with empty strings so index math is safe."""
    out = [str(n) for n in names][:NUM_PORTS]
    out += [""] * (NUM_PORTS - len(out))
    return out


def _extract_names(body: dict) -> tuple[list[str] | None, list[str] | None]:
    """Pull (input_names, output_names) out of a single device body, if present.

    The BK808 carries its port names in more than one place depending on
    which sticky response is returned:
      * `allinputname` / `alloutputname`  (the `get video status` blob)
      * `inname`                          (the `get input status` blob)
      * `name`                            (the `get output status` blob)
    We accept whichever of those keys are present and are non-empty lists.
    Either returned value may be None when that body did not carry it.
    """
    input_names = output_names = None
    if isinstance(body, dict):
        for key in ("allinputname", "inname"):
            val = body.get(key)
            if isinstance(val, list) and any(str(n).strip() for n in val):
                input_names = list(val)
                break
        for key in ("alloutputname", "name"):
            val = body.get(key)
            if isinstance(val, list) and any(str(n).strip() for n in val):
                output_names = list(val)
                break
    return input_names, output_names


async def _validate(host: str) -> dict:
    """Reach the matrix and gather its port names (best effort).

    Returns {"input_names": [...], "output_names": [...]} — either list may
    be empty. The device is single-connection and sticky: it latches whatever
    blob it last generated regardless of the `comhead` we ask for. So we try
    several `comhead`s, merge the name sets we do find, and treat reachability
    (a 200 JSON body) as the success criterion, not the presence of names.
    """
    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
    base = f"https://{host}"
    input_names: list[str] | None = None
    output_names: list[str] | None = None

    async def _get(comhead: str) -> dict | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base}/cgi-bin/query",
                    params={"comhead": comhead},
                    timeout=timeout,
                    ssl=False,
                ) as resp:
                    resp.raise_for_status()
                    return json.loads(await resp.text())
        except (aiohttp.ClientError, aiohttp.ServerTimeoutError, ValueError):
            return None

    async def _post(comhead: str) -> dict | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base}/cgi-bin/instr",
                    json={"comhead": comhead},
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=timeout,
                    ssl=False,
                ) as resp:
                    resp.raise_for_status()
                    return json.loads(await resp.text())
        except (aiohttp.ClientError, aiohttp.ServerTimeoutError, ValueError):
            return None

    def _merge(body: dict | None) -> None:
        nonlocal input_names, output_names
        if body is None:
            return
        in_names, out_names = _extract_names(body)
        if input_names is None and in_names:
            input_names = in_names
        if output_names is None and out_names:
            output_names = out_names

    # Pass 1: the GET-based endpoints. On this device a `get video status`
    # blob carries both `allinputname` and `alloutputname`; that's the
    # reliable source for *both*.
    for comhead in (
        "get video status",
        "get cec status",
        "get input status",
        "get output status",
    ):
        _merge(await _get(comhead))
        if input_names and output_names:
            break  # have both; done.

    # Pass 2: the sticky device sometimes latches one response and keeps
    # returning it regardless of `comhead`, so a GET may not have handed us
    # the input names. POST to /cgi-bin/instr reliably yields the specific
    # blob we ask for — use it for whichever name set is still missing.
    #
    # NOTE (sticky-socket interlock): this function finishes on a POST, which
    # leaves the device latched on a NON-video blob right before setup runs.
    # That's safe ONLY because the coordinator's initial read also POSTs (see
    # coordinator._read_video_blob) to re-latch. If anyone ever makes setup
    # read the routing state via GET, this trailing POST will make it fail
    # with "device unreachable". Keep the two in step — the coordinator's
    # comment cross-references this one.
    if not input_names:
        _merge(await _post("get input status"))
    if not output_names:
        _merge(await _post("get output status"))

    return {
        "input_names": input_names or [],
        "output_names": output_names or [],
    }


class OreiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User-initiated setup.

    Step 1 (`user`):  ask for the host.
    Step 2 (`naming`): show the device-reported port names, pre-filled in
                       both input and output fields; the user may rename
                       any of them or leave a slot blank to fall back to
                       the device name.
    """

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (
                user_input[CONF_HOST]
                .strip()
                .removeprefix("https://")
                .removeprefix("http://")
            )
            self._host = host
            try:
                state = await _validate(host)
            except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
                _LOGGER.error("Cannot reach %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Unexpected error contacting %s: %s", host, err, exc_info=True
                )
                errors["base"] = "unknown"
            else:
                # Stash the device-reported names (may be empty) so the
                # naming step can pre-fill them.
                self._device_input_names = _pad_names(
                    list(state.get("input_names", []))
                )
                self._device_output_names = _pad_names(
                    list(state.get("output_names", []))
                )
                return await self.async_step_naming()

            # If we got here one of the error branches ran. Re-show the
            # user form on the next submit.
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_naming(self, user_input: dict | None = None) -> dict:
        """Rename step. The text fields are the source of truth and are
        pre-filled with the device's own port names, so:
          * do nothing  -> the device's names are used (they "pull perfectly"),
          * edit fields -> your names are used (no hidden toggle to trip on).
        We intentionally do *not* keep a "use device names" checkbox here:
        the fields already contain the device names, so a boolean that either
        overwrites or preserves them is redundant and was the source of both
        the "checkbox always looks unchecked" confusion and the earlier
        "several attempts" bug (a checked box silently discarding edits).
        """
        device_in = ",".join(n for n in self._device_input_names if n.strip())
        device_out = ",".join(n for n in self._device_output_names if n.strip())
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_INPUT_NAMES,
                    default=device_in if device_in else ",".join(DEFAULT_INPUT_NAMES),
                ): str,
                vol.Optional(
                    CONF_OUTPUT_NAMES,
                    default=(
                        device_out if device_out else ",".join(DEFAULT_OUTPUT_NAMES)
                    ),
                ): str,
            }
        )

        if user_input is not None:
            # The text fields are authoritative — whatever the user left in them.
            chosen_in = _split_names(user_input.get(CONF_INPUT_NAMES, ""))
            chosen_out = _split_names(user_input.get(CONF_OUTPUT_NAMES, ""))

            # Pad to NUM_PORTS so the coordinator's index math is safe even
            # if the user left trailing slots blank.
            chosen_in = _pad_names(chosen_in)
            chosen_out = _pad_names(chosen_out)

            # Fall back to generic names for any blank slots so the
            # coordinator never sees an empty string.
            chosen_in = [n or f"Input {i+1}" for i, n in enumerate(chosen_in)]
            chosen_out = [n or f"Output {i+1}" for i, n in enumerate(chosen_out)]

            self._async_abort_entries_match({CONF_HOST: self._host})
            return self.async_create_entry(
                title=self._host,
                data={
                    CONF_HOST: self._host,
                    CONF_INPUT_NAMES: chosen_in,
                    CONF_OUTPUT_NAMES: chosen_out,
                    # Keep the device-reported names around so the user can
                    # switch back to them later from the options flow.
                    "device_input_names": list(self._device_input_names),
                    "device_output_names": list(self._device_output_names),
                },
            )

        return self.async_show_form(
            step_id="naming",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OreiOptionsFlowHandler(config_entry)


class OreiOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow — rename inputs and outputs (or revert to device names)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> dict:
        entry = self._config_entry
        cur_in = _names_to_display(entry.data.get(CONF_INPUT_NAMES))
        cur_out = _names_to_display(entry.data.get(CONF_OUTPUT_NAMES))
        dev_in = _names_to_display(entry.data.get("device_input_names"))
        dev_out = _names_to_display(entry.data.get("device_output_names"))

        schema = vol.Schema(
            {
                vol.Required(CONF_INPUT_NAMES, default=cur_in): str,
                vol.Required(CONF_OUTPUT_NAMES, default=cur_out): str,
                vol.Optional(
                    "use_device_names",
                    default=bool(dev_in and dev_out),
                ): bool,
            }
        )

        if user_input is not None:
            if user_input.get("use_device_names", False) and dev_in and dev_out:
                chosen_in = _pad_names(
                    [n for n in (entry.data.get("device_input_names") or []) if n]
                )
                chosen_out = _pad_names(
                    [n for n in (entry.data.get("device_output_names") or []) if n]
                )
            else:
                chosen_in = _split_names(user_input.get(CONF_INPUT_NAMES, ""))
                chosen_out = _split_names(user_input.get(CONF_OUTPUT_NAMES, ""))
            chosen_in = [
                n or f"Input {i+1}" for i, n in enumerate(_pad_names(chosen_in))
            ]
            chosen_out = [
                n or f"Output {i+1}" for i, n in enumerate(_pad_names(chosen_out))
            ]

            data = dict(entry.data)
            data[CONF_INPUT_NAMES] = chosen_in
            data[CONF_OUTPUT_NAMES] = chosen_out
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="init", data_schema=schema)
