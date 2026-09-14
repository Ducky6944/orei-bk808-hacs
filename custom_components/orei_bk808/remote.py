"""Remote selects — one "remote" select per port to collapse the CEC buttons.

Input N  -> select.input_N_remote   : every input-side CEC command
Output N -> select.output_N_remote  : the 8 routing inputs (stateful)
                                       + Mute / Unmute
                                       + every output-side CEC command

Pick an option and it fires. Routing options double as the live state read
(they track the real route, just like the dedicated route select).
"""

import logging

from homeassistant.components.select import SelectEntity
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

MUTE_LABEL = "Mute"
UNMUTE_LABEL = "Unmute"


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
        InputRemoteSelect(coordinator, n, hostname) for n in range(1, NUM_PORTS + 1)
    ]
    entities += [
        OutputRemoteSelect(coordinator, n, hostname) for n in range(1, NUM_PORTS + 1)
    ]
    async_add_entities(entities)


class InputRemoteSelect(SelectEntity, CoordinatorEntity):
    """One dropdown per input port listing every input-side CEC command."""

    def __init__(self, coordinator, port_num: int, hostname: str):
        super().__init__(coordinator)
        self._port = port_num
        self._attr_name = f"Input {port_num} Remote"
        self._attr_unique_id = f"{hostname}_input_{port_num}_remote"
        self._attr_icon = "mdi:remote"
        self._label_to_cmd = {
            label: cmd for cmd, (_idx, _icon, label) in CEC_INPUT_COMMANDS.items()
        }

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def options(self) -> list:
        order = [
            "power_on", "power_off", "play", "pause", "stop", "next_track",
            "prev_track", "rewind", "fast_forward", "mute",
            "volume_up", "volume_down", "menu", "enter", "up", "down",
            "left", "right", "loop",
        ]
        opts = []
        for cmd in order + list(CEC_INPUT_COMMANDS):
            if cmd not in CEC_INPUT_COMMANDS:
                continue
            _idx, _icon, label = CEC_INPUT_COMMANDS[cmd]
            if label not in opts:
                opts.append(label)
        return opts

    @property
    def current_option(self) -> str | None:
        # Pure fire-and-forget select; nothing to hold.
        return None

    async def async_select_option(self, option: str) -> None:
        cmd = self._label_to_cmd.get(option)
        if cmd is None:
            _LOGGER.warning("Input %d remote: unknown option %r", self._port, option)
            return
        await self.coordinator.send_cec("input", self._port, cmd)
        _LOGGER.info("Input %d remote -> %s", self._port, cmd)


class OutputRemoteSelect(SelectEntity, CoordinatorEntity):
    """One dropdown per output port: routing + mute + output-side CEC.

    The routing options reflect live state (same as the route select),
    so this dropdown doubles as the state read for the output.
    """

    def __init__(self, coordinator, port_num: int, hostname: str):
        super().__init__(coordinator)
        self._out = port_num
        self._attr_name = f"Output {port_num} Remote"
        self._attr_unique_id = f"{hostname}_output_{port_num}_remote"
        self._attr_icon = "mdi:remote"
        self._label_to_cmd = {
            label: cmd for cmd, (_idx, _icon, label) in CEC_OUTPUT_COMMANDS.items()
        }

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    @property
    def routing_options(self) -> list[str]:
        return [
            self.coordinator.input_display_name(i)
            for i in range(1, NUM_PORTS + 1)
        ]

    @property
    def options(self) -> list:
        cec_order = [
            "power_on", "power_off", "play", "pause", "next_track",
            "prev_track", "mute", "volume_up", "volume_down", "enter",
            "menu", "loop", "left", "right", "down",
        ]
        cec_options = []
        for cmd in cec_order + list(CEC_OUTPUT_COMMANDS):
            if cmd not in CEC_OUTPUT_COMMANDS:
                continue
            _idx, _icon, label = CEC_OUTPUT_COMMANDS[cmd]
            if label not in cec_options:
                cec_options.append(label)
        opts = [
            *self.routing_options,
            MUTE_LABEL,
            UNMUTE_LABEL,
            *cec_options,
        ]
        # De-dup in case a user named an input after one of the action
        # labels (routing name would be returned first and win the match).
        seen = set()
        out = []
        for o in opts:
            if o not in seen:
                seen.add(o)
                out.append(o)
        return out

    @property
    def current_option(self) -> str | None:
        inum = self.coordinator.get_routed_input(self._out)
        if inum is not None and 1 <= inum <= NUM_PORTS:
            return self.coordinator.input_display_name(inum)
        return None

    async def async_select_option(self, option: str) -> None:
        # Routing first: user-named inputs take priority over the fixed
        # action labels so an input literally named "Mute" still routes.
        routing = list(self.routing_options)
        if option in routing:
            await self.coordinator.set_route(self._out, routing.index(option) + 1)
            _LOGGER.info("Output %d routed to %s", self._out, option)
            return
        if option == MUTE_LABEL:
            await self.coordinator.set_mute(self._out, True)
            return
        if option == UNMUTE_LABEL:
            await self.coordinator.set_mute(self._out, False)
            return

        cmd = self._label_to_cmd.get(option)
        if cmd is None:
            _LOGGER.warning("Output %d remote: unknown option %r", self._out, option)
            return
        await self.coordinator.send_cec("output", self._out, cmd)
        _LOGGER.info("Output %d remote -> %s", self._out, cmd)
        self.async_write_ha_state()
