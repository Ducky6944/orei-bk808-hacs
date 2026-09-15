"""Switch platform — matrix power + per-output audio mute."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [MatrixPower(coordinator)]
    for o in range(1, NUM_PORTS + 1):
        entities.append(OutputMute(coordinator, o))
    async_add_entities(entities)


class MatrixPower(SwitchEntity, CoordinatorEntity):
    """Matrix power on/off (standby)."""

    _attr_icon = "mdi:power"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        hostname = str(coordinator.host).replace(".", "_")
        self._attr_unique_id = f"{hostname}_power"

    @property
    def name(self) -> str:
        return "Matrix Power"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.get_power()

    async def async_turn_on(self) -> None:
        await self.coordinator.set_power(True)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        await self.coordinator.set_power(False)
        self.async_write_ha_state()


class OutputMute(SwitchEntity, CoordinatorEntity):
    """Audio mute per output."""

    _attr_icon = "mdi:speaker"

    def __init__(self, coordinator, output_num: int):
        super().__init__(coordinator)
        self._out = output_num
        hostname = str(coordinator.host).replace(".", "_")
        self._attr_unique_id = f"{hostname}_output_{output_num}_mute"
        self._muted = (
            False  # best-effort; the device doesn't expose a per-output mute read
        )

    @property
    def name(self) -> str:
        return f"{self.coordinator.output_display_name(self._out)} Mute"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def is_on(self) -> bool:
        return self._muted

    async def async_turn_on(self) -> None:
        self._muted = True
        await self.coordinator.set_mute(self._out, True)
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        self._muted = False
        await self.coordinator.set_mute(self._out, False)
        self.async_write_ha_state()
