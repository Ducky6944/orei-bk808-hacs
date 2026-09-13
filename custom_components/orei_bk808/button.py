"""Button platform for all CEC commands."""

import logging
from typing import Any
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, DEFAULT_INPUT_NAMES, DEFAULT_OUTPUT_NAMES,
    INPUT_CEC_GROUPS, OUTPUT_CEC_GROUPS
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up all CEC buttons for inputs and outputs."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    input_names = entry.data.get("input_names", DEFAULT_INPUT_NAMES)
    output_names = entry.data.get("output_names", DEFAULT_OUTPUT_NAMES)
    
    entities = []
    
    for input_num in range(1, 9):
        input_name = input_names[input_num - 1] if input_num <= len(input_names) else f"Input {input_num}"
        
        for category, buttons in INPUT_CEC_GROUPS.items():
            for cmd, icon in buttons:
                entities.append(
                    InputCecButton(coordinator, input_num, input_name, cmd, icon, category)
                )
    
    for output_num in range(1, 9):
        output_name = output_names[output_num - 1] if output_num <= len(output_names) else f"Output {output_num}"
        
        for category, buttons in OUTPUT_CEC_GROUPS.items():
            for cmd, icon in buttons:
                entities.append(
                    OutputCecButton(coordinator, output_num, output_name, cmd, icon, category)
                )
    
    for action_name, actions in QUICK_ACTIONS.items():
        entities.append(QuickActionButton(coordinator, action_name, actions))
    
    async_add_entities(entities, True)

class InputCecButton(ButtonEntity):
    """CEC command button for input devices."""
    
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, input_num: int, input_name: str, 
                 command: str, icon: str, category: str):
        self.coordinator = coordinator
        self.input_num = input_num
        self.input_name = input_name
        self.command = command
        self.category = category
        
        self._attr_unique_id = f"{coordinator.host}_input_{input_num}_{category}_{command}"
        self._attr_translation_key = f"input_{input_num}_{category}_{command}"
        self._attr_name = f"{input_name} - {command.replace('_', ' ').title()}"
        self._attr_icon = icon
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 - {self.input_name}",
            manufacturer="Orei",
            model="BK808",
            via_device=(DOMAIN, self.coordinator.host),
            configuration_url=f"https://{self.coordinator.host}",
        )
    
    async def async_press(self) -> None:
        """Send CEC command to input when button pressed."""
        try:
            await self.coordinator.send_input_cec(self.input_num, self.command)
            _LOGGER.debug("Sent %s CEC to %s (Input %d)", 
                         self.command, self.input_name, self.input_num)
        except Exception as e:
            _LOGGER.error("Failed to send CEC command: %s", e)

class OutputCecButton(ButtonEntity):
    """CEC command button for output devices."""
    
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, output_num: int, output_name: str,
                 command: str, icon: str, category: str):
        self.coordinator = coordinator
        self.output_num = output_num
        self.output_name = output_name
        self.command = command
        self.category = category
        
        self._attr_unique_id = f"{coordinator.host}_output_{output_num}_{category}_{command}"
        self._attr_translation_key = f"output_{output_num}_{category}_{command}"
        self._attr_name = f"{output_name} - {command.replace('_', ' ').title()}"
        self._attr_icon = icon
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 - {self.output_name}",
            manufacturer="Orei",
            model="BK808",
            via_device=(DOMAIN, self.coordinator.host),
            configuration_url=f"https://{self.coordinator.host}",
        )
    
    async def async_press(self) -> None:
        """Send CEC command to output when button pressed."""
        try:
            await self.coordinator.send_output_cec(self.output_num, self.command)
            _LOGGER.debug("Sent %s CEC to %s (Output %d)",
                         self.command, self.output_name, self.output_num)
        except Exception as e:
            _LOGGER.error("Failed to send CEC command: %s", e)

class QuickActionButton(ButtonEntity):
    """Predefined quick action macro buttons."""
    
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, action_name: str, actions: list):
        self.coordinator = coordinator
        self.action_name = action_name
        self.actions = actions
        
        self._attr_unique_id = f"{coordinator.host}_quick_action_{action_name}"
        self._attr_name = action_name.replace('_', ' ').title()
        self._attr_icon = "mdi:application-outline"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 ({self.coordinator.host})",
            manufacturer="Orei",
            model="BK808",
            hw_version="8x8 Matrix",
            sw_version="1.0",
            configuration_url=f"https://{self.coordinator.host}",
        )
    
    async def async_press(self) -> None:
        """Execute sequence of actions."""
        for action, target in self.actions:
            await self.coordinator.execute_quick_action(action, target)
