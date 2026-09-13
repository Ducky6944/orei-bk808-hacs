"""Config flow for Orei BK808 integration."""

import logging
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol
import aiohttp
import asyncio
import base64

from .const import (
    DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
    CONF_INPUT_NAMES, CONF_OUTPUT_NAMES,
    DEFAULT_INPUT_NAMES, DEFAULT_OUTPUT_NAMES
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

STEP_NAMING_SCHEMA = vol.Schema({
    vol.Optional(CONF_INPUT_NAMES): str,
    vol.Optional(CONF_OUTPUT_NAMES): str,
})

class OreiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Installation wizard for Orei BK808 Matrix Controller."""
    
    VERSION = 1
    
    def __init__(self):
        self.user_input = {}
        self.test_result = None
        self.device_info = {}
    
    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Step 1: Enter connection details."""
        errors = {}
        
        if user_input is not None:
            self.user_input.update(user_input)
            return await self.async_step_test_connection()
        
        return self.async_show_form(
            step_id="user",
            title="🔌 Orei BK808 Setup - Step 1",
            description="Enter your matrix IP address and credentials. "
                       "This wizard will guide you through configuration.",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
    
    async def async_step_test_connection(self, user_input: dict | None = None) -> FlowResult:
        """Step 2: Test the connection and show device info."""
        errors = {}
        
        try:
            auth_header = base64.b64encode(
                f"{self.user_input[CONF_USERNAME]}:{self.user_input[CONF_PASSWORD]}".encode()
            ).decode()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://{self.user_input[CONF_HOST]}/cgi-bin/instr",
                    headers={
                        "Authorization": f"Basic {auth_header}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={"comhead": "get system status", "language": 0},
                    timeout=10,
                    ssl=False,
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        self.test_result = result.get("result", {})
                        
                        # Extract device information for display
                        self.device_info = {
                            "firmware": self.test_result.get("version", "Unknown"),
                            "power": "ON" if self.test_result.get("power", 0) else "OFF",
                            "model": "BK808",
                            "manufacturer": "Orei",
                        }
                        
                        return await self.async_step_naming()
                    else:
                        raise Exception(f"HTTP {resp.status}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            errors["base"] = "cannot_connect"
            _LOGGER.error("Connection test failed: %s", e)
            return self.async_show_form(
                step_id="test_connection",
                title="❌ Connection Failed",
                description="Could not reach the matrix. Please check:\n"
                          "• IP address is correct\n"
                          "• Matrix is powered on\n"
                          "• Firewall allows HTTPS (port 443)\n"
                          "• Credentials are correct",
                data_schema={},
                errors=errors,
            )
        except Exception as e:
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="test_connection",
                title="❌ Unknown Error",
                description=f"An error occurred: {str(e)}",
                data_schema={},
                errors=errors,
            )
    
    async def async_step_naming(self, user_input: dict | None = None) -> FlowResult:
        """Step 3: Customize input/output names."""
        errors = {}
        
        if user_input is not None:
            # Parse comma-separated names
            if user_input.get(CONF_INPUT_NAMES):
                input_names = [n.strip() for n in user_input[CONF_INPUT_NAMES].split(",")][:8]
                input_names.extend(DEFAULT_INPUT_NAMES[len(input_names):])
                self.user_input[CONF_INPUT_NAMES] = input_names[:8]
            else:
                self.user_input[CONF_INPUT_NAMES] = DEFAULT_INPUT_NAMES
            
            if user_input.get(CONF_OUTPUT_NAMES):
                output_names = [n.strip() for n in user_input[CONF_OUTPUT_NAMES].split(",")][:8]
                output_names.extend(DEFAULT_OUTPUT_NAMES[len(output_names):])
                self.user_input[CONF_OUTPUT_NAMES] = output_names[:8]
            else:
                self.user_input[CONF_OUTPUT_NAMES] = DEFAULT_OUTPUT_NAMES
            
            return await self.async_step_final()
        
        # Show defaults and device info
        default_inputs = ", ".join(DEFAULT_INPUT_NAMES)
        default_outputs = ", ".join(DEFAULT_OUTPUT_NAMES)
        
        return self.async_show_form(
            step_id="naming",
            title="✅ Connection Successful!",
            description=f"**Device Found!**\n\n"
                       f"• **Model:** {self.device_info['model']}\n"
                       f"• **Firmware:** {self.device_info['firmware']}\n"
                       f"• **Status:** {self.device_info['power']}\n"
                       f"• **IP:** {self.user_input[CONF_HOST]}\n\n"
                       f"Customize input/output names below (optional). "
                       f"Enter 8 comma-separated names or leave blank for defaults.\n\n"
                       f"*Example: PS5, Xbox, Gaming PC, Apple TV*",
            data_schema=STEP_NAMING_SCHEMA,
            data_defaults={
                CONF_INPUT_NAMES: default_inputs,
                CONF_OUTPUT_NAMES: default_outputs,
            },
            errors=errors,
        )
    
    async def async_step_final(self, user_input: dict | None = None) -> FlowResult:
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
        self.config_entry = config_entry
    
    async def async_step_init(self, user_input=None):
        """Manage options."""
        errors = {}
        
        if user_input is not None:
            new_data = {**self.config_entry.data}
            
            if CONF_INPUT_NAMES in user_input and user_input[CONF_INPUT_NAMES]:
                input_names = [n.strip() for n in user_input[CONF_INPUT_NAMES].split(",")][:8]
                new_data[CONF_INPUT_NAMES] = input_names
            
            if CONF_OUTPUT_NAMES in user_input and user_input[CONF_OUTPUT_NAMES]:
                output_names = [n.strip() for n in user_input[CONF_OUTPUT_NAMES].split(",")][:8]
                new_data[CONF_OUTPUT_NAMES] = output_names
            
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            
            return self.async_create_entry(title="", data={})
        
        current_inputs = self.config_entry.data.get(CONF_INPUT_NAMES, DEFAULT_INPUT_NAMES)
        current_outputs = self.config_entry.data.get(CONF_OUTPUT_NAMES, DEFAULT_OUTPUT_NAMES)
        
        return self.async_show_form(
            step_id="init",
            title="⚙️ Orei BK808 Settings",
            description="Update input/output names.",
            data_schema=vol.Schema({
                vol.Optional(CONF_INPUT_NAMES): 
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Optional(CONF_OUTPUT_NAMES): 
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            }),
            data_defaults={
                CONF_INPUT_NAMES: ", ".join(current_inputs),
                CONF_OUTPUT_NAMES: ", ".join(current_outputs),
            },
            errors=errors,
        )
