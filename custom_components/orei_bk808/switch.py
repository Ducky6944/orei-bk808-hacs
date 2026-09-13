"""Switch platform for Orei BK808 power/mute/ARC controls."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEFAULT_OUTPUT_NAMES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    entities.append(MatrixPowerSwitch(coordinator))

    output_names = entry.data.get("output_names", DEFAULT_OUTPUT_NAMES)
    for output_num in range(1, 9):
        output_name = output_names[output_num - 1] if output_num <= len(output_names) else f"Output {output_num}"
        entities.append(ToggleSwitch(coordinator, output_num, output_name, "arc"))
        entities.append(ToggleSwitch(coordinator, output_num, output_name, "mute"))

    async_add_entities(entities)


class MatrixPowerSwitch(SwitchEntity):
    """Master power switch for the matrix."""

    _attr_has_entity_name = True
    _attr_name = "Matrix Power"
    _attr_icon = "mdi:television"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_unique_id = f"orei_{coordinator.host}_power"
        self._attr_is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 ({self.coordinator.host})",
            manufacturer="Orei",
            model="BK808",
            configuration_url=f"https://{self.coordinator.host}",
        )

    async def async_turn_on(self):
        """Turn matrix on."""
        await self.coordinator.power_matrix(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn matrix off."""
        await self.coordinator.power_matrix(False)
        self._attr_is_on = False
        self.async_write_ha_state()


class ToggleSwitch(SwitchEntity):
    """Generic toggle switch for output features (ARC, mute)."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator, output_num: int, output_name: str, toggle_type: str):
        self.coordinator = coordinator
        self.output_num = output_num
        self.output_name = output_name
        self.toggle_type = toggle_type

        self._attr_unique_id = f"orei_{coordinator.host}_output_{output_num}_{toggle_type}"
        self._attr_name = f"{output_name} - {toggle_type.title()}"
        self._attr_is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 - {self.output_name}",
            manufacturer="Orei",
            model="BK808",
        )

    async def async_turn_on(self):
        await self.coordinator.send_command(f"set {self.toggle_type}", port=self.output_num, state=1)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        await self.coordinator.send_command(f"set {self.toggle_type}", port=self.output_num, state=0)
        self._attr_is_on = False
        self.async_write_ha_state()
