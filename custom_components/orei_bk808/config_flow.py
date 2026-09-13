"""Config flow for Orei BK808 integration."""

import logging
import aiohttp

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN, CONF_HOST,
    CONF_INPUT_NAMES, CONF_OUTPUT_NAMES,
    DEFAULT_INPUT_NAMES, DEFAULT_OUTPUT_NAMES,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class OreiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Installation wizard for Orei BK808 Matrix Controller."""

    VERSION = 1

    def __init__(self):
        self.user_input = {}
        self.device_info = {}

    async def async_step_user(self, user_input=None):
        """Step 1: Enter the matrix IP address."""
        errors = {}

        if user_input is not None:
            self.user_input.update(user_input)
            return await self.async_step_test_connection()

        import voluptuous as vol
        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_test_connection(self, user_input=None):
        """Step 2: Test the connection and show device info."""
        errors = {}

        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://{self.user_input[CONF_HOST]}/cgi-bin/instr",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={"comhead": "get system status", "language": 0},
                    timeout=timeout,
                    ssl=False,
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.device_info = {
                            "firmware": result.get("version", "Unknown"),
                            "power": "ON" if result.get("power", 0) else "OFF",
                            "model": "BK808",
                            "manufacturer": "Orei",
                        }
                        return await self.async_step_naming()
                    else:
                        raise Exception(f"HTTP {resp.status}")

        except (aiohttp.ClientError, aiohttp.ServerTimeoutError) as e:
            errors["base"] = "cannot_connect"
            _LOGGER.error("Connection test failed: %s", e)
            import voluptuous as vol
            return self.async_show_form(
                step_id="test_connection",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                }),
                errors=errors,
            )
        except Exception as e:
            errors["base"] = "unknown"
            _LOGGER.error("Unexpected error: %s", e)
            import voluptuous as vol
            return self.async_show_form(
                step_id="test_connection",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                }),
                errors=errors,
            )

    async def async_step_naming(self, user_input=None):
        """Step 3: Customize input/output names."""
        errors = {}

        if user_input is not None:
            if user_input.get(CONF_INPUT_NAMES):
                input_names = [n.strip() for n in user_input[CONF_INPUT_NAMES].split(",")][:8]
                input_names.extend(DEFAULT_INPUT_NAMES[len(input_names):])
                self.user_input[CONF_INPUT_NAMES] = input_names[:8]
            else:
                self.user_input[CONF_INPUT_NAMES] = list(DEFAULT_INPUT_NAMES)

            if user_input.get(CONF_OUTPUT_NAMES):
                output_names = [n.strip() for n in user_input[CONF_OUTPUT_NAMES].split(",")][:8]
                output_names.extend(DEFAULT_OUTPUT_NAMES[len(output_names):])
                self.user_input[CONF_OUTPUT_NAMES] = output_names[:8]
            else:
                self.user_input[CONF_OUTPUT_NAMES] = list(DEFAULT_OUTPUT_NAMES)

            return await self.async_step_final()

        default_inputs = ", ".join(DEFAULT_INPUT_NAMES)
        default_outputs = ", ".join(DEFAULT_OUTPUT_NAMES)

        import voluptuous as vol
        schema = vol.Schema({
            vol.Optional(CONF_INPUT_NAMES, default=default_inputs): str,
            vol.Optional(CONF_OUTPUT_NAMES, default=default_outputs): str,
        })

        return self.async_show_form(
            step_id="naming",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_final(self, user_input=None):
        """Final step: Confirm and create."""
        await self.async_set_unique_id(self.user_input[CONF_HOST])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.user_input[CONF_HOST],
            data=self.user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for reconfiguration."""
        return OreiOptionsFlowHandler(config_entry)


class OreiOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for renaming inputs/outputs."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        errors = {}

        import voluptuous as vol

        if user_input is not None:
            new_data = dict(self._config_entry.data)

            if user_input.get(CONF_INPUT_NAMES):
                input_names = [n.strip() for n in user_input[CONF_INPUT_NAMES].split(",")][:8]
                input_names.extend(DEFAULT_INPUT_NAMES[len(input_names):])
                new_data[CONF_INPUT_NAMES] = input_names[:8]

            if user_input.get(CONF_OUTPUT_NAMES):
                output_names = [n.strip() for n in user_input[CONF_OUTPUT_NAMES].split(",")][:8]
                output_names.extend(DEFAULT_OUTPUT_NAMES[len(output_names):])
                new_data[CONF_OUTPUT_NAMES] = output_names[:8]

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        current_inputs = self._config_entry.data.get(CONF_INPUT_NAMES, DEFAULT_INPUT_NAMES)
        current_outputs = self._config_entry.data.get(CONF_OUTPUT_NAMES, DEFAULT_OUTPUT_NAMES)

        if isinstance(current_inputs, list):
            current_inputs = ", ".join(current_inputs)
        if isinstance(current_outputs, list):
            current_outputs = ", ".join(current_outputs)

        schema_defaults = vol.Schema({
            vol.Optional(CONF_INPUT_NAMES, default=current_inputs): str,
            vol.Optional(CONF_OUTPUT_NAMES, default=current_outputs): str,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema_defaults,
            errors=errors,
        )
