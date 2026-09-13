"""Sensor platform for Orei BK808 status."""

import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up status sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        MatrixStatusSensor(coordinator),
        PresetStatusSensor(coordinator),
        ActiveInputsSensor(coordinator),
        ActiveOutputsSensor(coordinator),
    ]
    
    for i in range(1, 9):
        entities.append(OutputRoutingSensor(coordinator, i))
    
    async_add_entities(entities, True)

class MatrixStatusSensor(SensorEntity, CoordinatorEntity):
    """Main matrix status sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "matrix_status"
    _attr_name = "Matrix Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:network-check"
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_matrix_status"
    
    @property
    def native_value(self):
        status = self.coordinator._video_status
        power = status.get("power", 0)
        return "Online" if power else "Offline"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 ({self.coordinator.host})",
            manufacturer="Orei",
            model="BK808",
            hw_version="8x8 HDMI Matrix",
            configuration_url=f"https://{self.coordinator.host}",
        )

class PresetStatusSensor(SensorEntity, CoordinatorEntity):
    """Current preset slot sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "active_preset"
    _attr_name = "Active Preset"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bookmark"
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_active_preset"
    
    @property
    def native_value(self):
        status = self.coordinator._video_status
        allname = status.get("allname", [])
        return allname[-1] if allname else "None"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            via_device=(DOMAIN, self.coordinator.host),
        )

class ActiveInputsSensor(SensorEntity, CoordinatorEntity):
    """Active input devices sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "active_inputs"
    _attr_name = "Active Inputs"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:input-component"
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_active_inputs"
    
    @property
    def native_value(self) -> str:
        status = self.coordinator._video_status
        allsource = status.get("allsource", [])
        active_inputs = set()
        
        for mapping in allsource:
            if len(mapping) >= 2:
                input_num = mapping[0]
                active_inputs.add(self.coordinator.get_input_display_name(input_num))
        
        return ", ".join(sorted(active_inputs)) if active_inputs else "None"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            via_device=(DOMAIN, self.coordinator.host),
        )

class ActiveOutputsSensor(SensorEntity, CoordinatorEntity):
    """Active output devices sensor."""
    
    _attr_has_entity_name = True
    _attr_translation_key = "active_outputs"
    _attr_name = "Active Outputs"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:television"
    
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_active_outputs"
    
    @property
    def native_value(self) -> str:
        status = self.coordinator._video_status
        allsource = status.get("allsource", [])
        active_outputs = set()
        
        for mapping in allsource:
            if len(mapping) >= 2:
                output_num = mapping[1]
                active_outputs.add(self.coordinator.get_output_display_name(output_num))
        
        return ", ".join(sorted(active_outputs)) if active_outputs else "None"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            via_device=(DOMAIN, self.coordinator.host),
        )

class OutputRoutingSensor(SensorEntity, CoordinatorEntity):
    """Individual output routing status sensor."""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:swap-horizontal"
    
    def __init__(self, coordinator, output_num: int):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.output_num = output_num
        self._attr_translation_key = f"output_{output_num}_routing"
        self._attr_name = f"Output {output_num} Input"
        self._attr_unique_id = f"{coordinator.host}_output_{output_num}_routing_sensor"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self) -> str:
        routing = self.coordinator.get_routing_for_output(self.output_num)
        if routing:
            _, input_name = routing
            return input_name
        return "None"
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            via_device=(DOMAIN, self.coordinator.host),
            name=f"Orei BK808 - Output {self.output_num}",
        )
