"""Select platform for Orei BK808 routing controls."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up select platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for output_num in range(1, 9):
        entities.append(OutputRoutingSelect(coordinator, output_num))

    async_add_entities(entities)


class OutputRoutingSelect(SelectEntity):
    """Select entity to control which input is routed to this output."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator, output_num: int):
        self.coordinator = coordinator
        self.output_num = output_num
        self._attr_unique_id = f"orei_{coordinator.host}_output_{output_num}_routing"
        self._attr_name = f"Output {output_num} Source"
        self._attr_options = [str(k) for k in coordinator.inputs.keys()]

    @property
    def current_option(self) -> str | None:
        """Return current selected input as string."""
        routing = self.coordinator.get_routing_for_output(self.output_num)
        if routing:
            return str(routing[0])
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        input_num = int(option)
        await self.coordinator.route_video(input_num, self.output_num)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=f"Orei BK808 - Output {self.output_num}",
            manufacturer="Orei",
            model="BK808",
        )
