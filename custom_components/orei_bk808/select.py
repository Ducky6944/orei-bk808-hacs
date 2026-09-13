"""Select platform for Orei BK808 routing controls."""

import logging
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, DEFAULT_INPUT_NAMES, DEFAULT_OUTPUT_NAMES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    for output_num in range(1, 9):
        entities.append(OutputRoutingSelect(coordinator, output_num))
    
    entities.append(ActiveInputsSensor(coordinator))
    
    async_add_entities(entities, True)

class OutputRoutingSelect(SelectEntity):
    """Select entity to control which input is routed to this output."""
    
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, output_num: int):
        self.coordinator = coordinator
        self.output_num = output_num
        self._attr_unique_id = f"{coordinator.host}_output_{output_num}_routing"
        self._attr_translation_key = f"output_{output_num}_routing"
        self._attr_name = f"Output {output_num} Input"
        self._attr_options = list(coordinator.inputs.keys())
        self._attr_current_option = None
        self._attr_entity_category = EntityCategory.CONFIG
    
    @property
    def current_option(self) -> str:
        """Return current selected input."""
        routing = self.coordinator.get_routing_for_output(self.output_num)
        if routing:
            return str(routing[0])
        return None
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        input_num = int(option)
        await self.coordinator.route_video(input_num, self.output_num)
        await self.coordinator.get_video_status()
        self.async_write_ha_state()
    
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": f"Orei BK808 - Output {self.output_num}",
            "manufacturer": "Orei",
            "model": "BK808",
            "via_device": (DOMAIN, self.coordinator.host),
        }

class ActiveInputsSensor(SelectEntity):
    """Show active inputs."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "active_inputs"
    _attr_name = "Active Inputs"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_active_inputs"
        self._attr_options = list(coordinator.inputs.values())
        self._attr_current_option = None
    
    @property
    def current_option(self) -> str:
        """Return currently active input."""
        if hasattr(self.coordinator, '_video_status') and self.coordinator._video_status:
            allsource = self.coordinator._video_status.get('allsource', [])
            active_inputs = set()
            for mapping in allsource:
                if len(mapping) >= 2:
                    active_inputs.add(str(mapping[0]))
            if active_inputs:
                return ", ".join(active_inputs)
        return None
    
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "via_device": (DOMAIN, self.coordinator.host),
        }
