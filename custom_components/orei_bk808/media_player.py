"""Media player platform — group the per-port CEC controls into real players.

  media_player.input_<N>   : the *source* device on input port N.
      transport / volume / power all route CEC to that input.

  media_player.output_<N>  : the *sink* (display/AVR) on output port N.
      select_source picks which input is routed to it (the "input switcher"),
      and transport / volume / power send CEC to that output.

This is what lets you replace the wall of buttons with one media-player
card per port — HA's native media controls just work.
"""

import logging

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUM_PORTS

_LOGGER = logging.getLogger(__name__)

# --- Feature flags (resilient to HA moving the enum) --------------------------
# `MediaPlayerFeature` has lived in homeassistant.components.media_player for
# years, but recent HA builds have relocated it, which previously broke this
# platform with "cannot import name 'MediaPlayerFeature'". Import from the
# usual place first, and fall back to a value-compatible IntFlag so the
# advertised feature mask stays correct on every supported HA version.
try:
    from homeassistant.components.media_player import MediaPlayerFeature  # type: ignore
except ImportError:  # pragma: no cover - version fallback
    try:
        from homeassistant.components.media_player.const import (  # type: ignore
            MediaPlayerFeature,
        )
    except ImportError:
        from enum import IntFlag

        class MediaPlayerFeature(IntFlag):  # type: ignore
            NONE = 0
            VOLUME_SET = 1
            VOLUME_MUTE = 2
            PLAY_MEDIA = 16
            PAUSE = 128
            PLAY = 256
            STOP = 512
            NEXT_TRACK = 1024
            PREVIOUS_TRACK = 2048
            SHUFFLE = 8192
            SELECT_SOURCE = 16384
            VOLUME_STEP = 32768
            TURN_OFF = 65536
            TURN_ON = 131072


# Media-player states as plain strings (the exact values HA expects) — avoids a
# hard dependency on the MediaPlayerState enum, which also moved across builds.
_STATE_IDLE = "idle"
_STATE_OFF = "off"


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
        _MediaInputPlayer(coordinator, n, hostname) for n in range(1, NUM_PORTS + 1)
    ]
    entities += [
        _MediaOutputPlayer(coordinator, n, hostname) for n in range(1, NUM_PORTS + 1)
    ]
    async_add_entities(entities)


class _BasePlayer(MediaPlayerEntity, CoordinatorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator, side: str, port: int, hostname: str):
        super().__init__(coordinator)
        self._side = side
        self._port = port
        self._hostname = hostname

    @property
    def device_info(self) -> DeviceInfo:
        return _dev(self.coordinator.host)

    async def _cec(self, command: str) -> None:
        try:
            await self.coordinator.send_cec(self._side, self._port, command)
            _LOGGER.info("media_player %s %d -> %s", self._side, self._port, command)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("CEC %s failed: %s", command, err, exc_info=True)



class _MediaInputPlayer(_BasePlayer):
    """A source device plugged into input port N."""

    _attr_supported_features = (
        MediaPlayerFeature.PLAY
        | MediaPlayerFeature.PAUSE
        | MediaPlayerFeature.STOP
        | MediaPlayerFeature.NEXT_TRACK
        | MediaPlayerFeature.PREVIOUS_TRACK
        | MediaPlayerFeature.VOLUME_MUTE
        | MediaPlayerFeature.VOLUME_STEP
        | MediaPlayerFeature.TURN_ON
        | MediaPlayerFeature.TURN_OFF
    )

    def __init__(self, coordinator, port: int, hostname: str):
        super().__init__(coordinator, "input", port, hostname)
        # Clean, deterministic name -> entity id media_player.input_<N>
        self._attr_name = f"Input {port}"
        self._attr_unique_id = f"{hostname}_input_{port}"

    @property
    def state(self) -> str | None:
        # The matrix doesn't report per-device playback state; show idle
        # while the source is routed somewhere, off otherwise.
        routed = any(
            self.coordinator.get_routed_input(o) == self._port
            for o in range(1, NUM_PORTS + 1)
        )
        return _STATE_IDLE if routed else _STATE_OFF

    @property
    def is_on(self) -> bool | None:
        return any(
            self.coordinator.get_routed_input(o) == self._port
            for o in range(1, NUM_PORTS + 1)
        )

    # ---- transport
    async def async_media_play(self) -> None:
        await self._cec("play")

    async def async_media_pause(self) -> None:
        await self._cec("pause")

    async def async_media_stop(self) -> None:
        await self._cec("stop")

    async def async_media_next_track(self) -> None:
        await self._cec("next_track")

    async def async_media_previous_track(self) -> None:
        await self._cec("prev_track")

    # ---- volume
    async def async_volume_up(self) -> None:
        await self._cec("volume_up")

    async def async_volume_down(self) -> None:
        await self._cec("volume_down")

    async def async_volume_mute(self, mute: bool) -> None:
        # The device exposes a single toggle; send it either way.
        await self._cec("mute")

    # ---- power
    async def async_turn_on(self) -> None:
        await self._cec("power_on")

    async def async_turn_off(self) -> None:
        await self._cec("power_off")


class _MediaOutputPlayer(_BasePlayer):
    """A sink (display / AVR) on output port N, with source selection."""

    _attr_supported_features = (
        MediaPlayerFeature.SELECT_SOURCE
        | MediaPlayerFeature.PLAY
        | MediaPlayerFeature.NEXT_TRACK
        | MediaPlayerFeature.PREVIOUS_TRACK
        | MediaPlayerFeature.VOLUME_MUTE
        | MediaPlayerFeature.VOLUME_STEP
        | MediaPlayerFeature.TURN_ON
        | MediaPlayerFeature.TURN_OFF
    )

    def __init__(self, coordinator, port: int, hostname: str):
        super().__init__(coordinator, "output", port, hostname)
        # Clean, deterministic name -> entity id media_player.output_<N>
        self._attr_name = f"Output {port}"
        self._attr_unique_id = f"{hostname}_output_{port}"

    @property
    def state(self) -> str | None:
        src = self.coordinator.get_routed_input(self._port)
        return _STATE_IDLE if src else _STATE_OFF

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.get_routed_input(self._port) is not None

    @property
    def source_list(self) -> list[str] | None:
        return [
            self.coordinator.input_display_name(i) for i in range(1, NUM_PORTS + 1)
        ]

    @property
    def source(self) -> str | None:
        src = self.coordinator.get_routed_input(self._port)
        if src is None:
            return None
        return self.coordinator.input_display_name(src)

    async def async_select_source(self, source: str) -> None:
        for i in range(1, NUM_PORTS + 1):
            if self.coordinator.input_display_name(i) == source:
                await self.coordinator.set_route(self._port, i)
                _LOGGER.info(
                    "output %d select_source -> %s", self._port, source
                )
                self.async_write_ha_state()
                return
        _LOGGER.warning("output %d select_source: unknown %r", self._port, source)

    # ---- transport (CEC to the sink)
    async def async_media_play(self) -> None:
        await self._cec("play")

    async def async_media_next_track(self) -> None:
        await self._cec("next_track")

    async def async_media_previous_track(self) -> None:
        await self._cec("prev_track")

    # ---- volume
    async def async_volume_up(self) -> None:
        await self._cec("volume_up")

    async def async_volume_down(self) -> None:
        await self._cec("volume_down")

    async def async_volume_mute(self, mute: bool) -> None:
        await self._cec("mute")

    # ---- power
    async def async_turn_on(self) -> None:
        await self._cec("power_on")

    async def async_turn_off(self) -> None:
        await self._cec("power_off")
