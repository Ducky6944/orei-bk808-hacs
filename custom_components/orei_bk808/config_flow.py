"""Config flow for the Orei BK808 HDMI Matrix."""

import json
import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_HOST,
    DEFAULT_INPUT_NAMES,
    DEFAULT_OUTPUT_NAMES,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

_NAME_SCHEMA = vol.Schema(
    {
        vol.Optional("input_names", default=",".join(DEFAULT_INPUT_NAMES)): str,
        vol.Optional("output_names", default=",".join(DEFAULT_OUTPUT_NAMES)): str,
    }
)


def _split_names(raw: str, fallback: list[str]) -> list[str]:
    names = [p.strip() for p in raw.split(",") if p.strip()][:8]
    names += fallback[len(names):]
    return names[:8]


async def _validate(host: str) -> dict:
    """Hit /cgi-bin/query and return the state body (throws on failure)."""
    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
    url = f"https://{host}/cgi-bin/query"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, params={"comhead": "get cec status"}, timeout=timeout, ssl=False
        ) as resp:
            resp.raise_for_status()
            return json.loads(await resp.text())


class OreiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """User-initiated setup: ask for the host, validate, finish."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> dict:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().removeprefix("https://").removeprefix("http://")
            try:
                state = await _validate(host)
            except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as err:
                _LOGGER.error("Cannot reach %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Unexpected error contacting %s: %s", host, err, exc_info=True)
                errors["base"] = "unknown"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                names = {
                    CONF_HOST: host,
                    "input_names": DEFAULT_INPUT_NAMES,
                    "output_names": DEFAULT_OUTPUT_NAMES,
                }
                # Store the device-reported names we saw, if any
                if "allinputname" in state:
                    names["input_names"] = list(state["allinputname"])[:8]
                if "alloutputname" in state:
                    names["output_names"] = list(state["alloutputname"])[:8]
                return self.async_create_entry(title=host, data=names)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OreiOptionsFlowHandler(config_entry)


class OreiOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow — rename inputs and outputs."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> dict:
        entry = self._config_entry
        cur_inputs = entry.data.get("input_names", DEFAULT_INPUT_NAMES)
        cur_outputs = entry.data.get("output_names", DEFAULT_OUTPUT_NAMES)
        if isinstance(cur_inputs, list):
            cur_inputs = ",".join(cur_inputs)
        if isinstance(cur_outputs, list):
            cur_outputs = ",".join(cur_outputs)

        if user_input is not None:
            data = dict(entry.data)
            data["input_names"] = _split_names(
                user_input.get("input_names", cur_inputs), DEFAULT_INPUT_NAMES
            )
            data["output_names"] = _split_names(
                user_input.get("output_names", cur_outputs), DEFAULT_OUTPUT_NAMES
            )
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = _NAME_SCHEMA
        return self.async_show_form(step_id="init", data_schema=schema)
