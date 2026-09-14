"""Sensor platform — matrix state readouts."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUM_PORTS

_LOGGER = logging.getLogger(__name__)


def _dev(host: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, host)},
        name=f"Orei BK808 ({host})",
        manufacturer="Orei",
        model="BK808",
        configuration_url=f"https://{host}",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    hostname = str(coordinator.host).replace(".", "_")
    entities: list = [
        PowerSensor(coordinator, hostname),
        FirmwareSensor(coordinator, hostname),
    ]
    for o in range(1, NUM_PORTS + 1):
        entities.append(OutputRoutedInputSensor(coordinator, o, hostname))
    async_add_entities(entities)


class PowerSensor(SensorEntity, CoordinatorEntity):
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator, hostname: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{hostname}_power"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def native_value(self) -> str:
        state = self.coordinator.get_power()
        if state is None:
            return "unknown"
        return "on" if state else "off"


class FirmwareSensor(SensorEntity, CoordinatorEntity):
    _attr_name = "Firmware"
    _attr_icon = "mdi:tag-multiple"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, hostname: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{hostname}_firmware"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def native_value(self) -> str | None:
        return self.coordinator._video_state.get("version")


class OutputRoutedInputSensor(SensorEntity, CoordinatorEntity):
    _attr_icon = "mdi:input-hdmi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, output_num: int, hostname: str):
        super().__init__(coordinator)
        self._out = output_num
        self._attr_name = f"Output {output_num} Routed Input"
        self._attr_unique_id = f"{hostname}_output_{output_num}_routed_input"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def native_value(self) -> str | None:
        inum = self.coordinator.get_routed_input(self._out)
        if inum is None:
            return "off"
        if not (1 <= inum <= NUM_PORTS):
            return f"source-{inum}"
        return self.coordinator.input_display_name(inum)
