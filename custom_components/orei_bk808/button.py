"""Button platform — one button per (port, CEC command)."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    NUM_PORTS,
    CEC_INPUT_COMMANDS,
    CEC_OUTPUT_COMMANDS,
)

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
    entities: list = []

    for inum in range(1, NUM_PORTS + 1):
        for cmd, (_idx, icon, label) in CEC_INPUT_COMMANDS.items():
            entities.append(
                CecButton(coordinator, "input", inum, cmd, label, icon, hostname)
            )

    for onum in range(1, NUM_PORTS + 1):
        for cmd, (_idx, icon, label) in CEC_OUTPUT_COMMANDS.items():
            entities.append(
                CecButton(coordinator, "output", onum, cmd, label, icon, hostname)
            )

    async_add_entities(entities)


class CecButton(ButtonEntity, CoordinatorEntity):
    """CEC button — sends a single CEC command to one input or output port."""


    def __init__(
        self,
        coordinator,
        side: str,
        port_num: int,
        cmd: str,
        label: str,
        icon: str,
        hostname: str,
    ):
        super().__init__(coordinator)
        self._side = side
        self._port = port_num
        self._cmd = cmd
        # Deterministic name derived from the command key so the generated
        # entity id is stable (e.g. button.input_1_prev_track).
        self._attr_name = f"{side.title()} {port_num} {cmd}"
        self._attr_icon = icon
        self._attr_unique_id = f"{hostname}_{side}_{port_num}_{cmd}"

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    async def async_press(self) -> None:
        try:
            await self.coordinator.send_cec(self._side, self._port, self._cmd)
            _LOGGER.info(
                "CEC %s %d -> %s", self._side.title(), self._port, self._cmd
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("CEC push failed: %s", err, exc_info=True)
