"""Select platform — one selector per output to choose the routed input.

The BK808 routes each output to one of 8 video inputs (1-8) or one of 8
audio/ARC sources (9-16). We expose the 8 video inputs here; audio/ARC
routing is available via the device's own web UI.
"""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUM_PORTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [OutputRouteSelect(coordinator, o) for o in range(1, NUM_PORTS + 1)]
    async_add_entities(entities)


class OutputRouteSelect(SelectEntity, CoordinatorEntity):
    _attr_icon = "mdi:input-hdmi"

    def __init__(self, coordinator, output_num: int):
        super().__init__(coordinator)
        self._out = output_num
        hostname = str(coordinator.host).replace(".", "_")
        self._attr_unique_id = f"{hostname}_output_{output_num}_route"

    @property
    def name(self) -> str:
        return f"Output {self._out} Route"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 ({self.coordinator.host})",
            manufacturer="Orei",
            model="BK808",
            configuration_url=f"https://{self.coordinator.host}",
        )

    @property
    def options(self) -> list:
        return [
            self.coordinator.input_display_name(i) for i in range(1, NUM_PORTS + 1)
        ]

    @property
    def current_option(self) -> str | None:
        inum = self.coordinator.get_routed_input(self._out)
        if inum is None or not (1 <= inum <= NUM_PORTS):
            return None
        return self.coordinator.input_display_name(inum)

    async def async_select_option(self, option: str) -> None:
        for i in range(1, NUM_PORTS + 1):
            if self.coordinator.input_display_name(i) == option:
                await self.coordinator.set_route(self._out, i)
                self.async_write_ha_state()
                return
        _LOGGER.warning("Unknown selection '%s' for output %d", option, self._out)
