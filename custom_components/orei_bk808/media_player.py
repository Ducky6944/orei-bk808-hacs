"""Media player platform — group the per-port CEC controls into real players.

  media_player.input_<N>   : the *source* device on input port N.
      transport / volume / power all route CEC to that input.

  media_player.output_<N>  : the *sink* (display/AVR) on output port N.
      select_source picks which input is routed to it (the "input switcher"),
      and transport / volume / power send CEC to that output.

This is what lets you replace the wall of buttons with one media-player
card per port — HA's native media controls just work.
"""

import asyncio
import logging
from pathlib import Path

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NUM_PORTS

_LOGGER = logging.getLogger(__name__)


# --- Feature flags (resilient to HA moving/renaming the enum) -----------------
# Current HA exports the flag as `MediaPlayerEntityFeature`, while older builds
# expose `MediaPlayerFeature`. We try both names in both the package and the
# `const` submodule, using whichever resolves (that guarantees values that
# match the running HA). Only if neither exists do we define a local IntFlag
# using the *current* (2026.x) bit values, so the advertised mask is still
# correct.
def _resolve_feature_flag():
    from homeassistant.components import media_player as _mp
    from homeassistant.components.media_player import const as _const

    for module in (_mp, _const):
        for name in ("MediaPlayerEntityFeature", "MediaPlayerFeature"):
            flag = getattr(module, name, None)
            if flag is not None:
                return flag
    from enum import IntFlag

    class _Feature(IntFlag):
        PAUSE = 1
        SEEK = 2
        VOLUME_SET = 4
        VOLUME_MUTE = 8
        PREVIOUS_TRACK = 16
        NEXT_TRACK = 32
        TURN_ON = 128
        TURN_OFF = 256
        PLAY_MEDIA = 512
        VOLUME_STEP = 1024
        SELECT_SOURCE = 2048
        STOP = 4096
        CLEAR_PLAYLIST = 8192
        PLAY = 16384
        SHUFFLE_SET = 32768
        SELECT_SOUND_MODE = 65536
        BROWSE_MEDIA = 131072
        REPEAT_SET = 262144
        GROUPING = 524288
        MEDIA_ANNOUNCE = 1048576
        MEDIA_ENQUEUE = 2097152
        SEARCH_MEDIA = 4194304

    _Feature.NONE = _Feature(0)  # type: ignore[attr-defined]
    return _Feature


MediaPlayerFeature = _resolve_feature_flag()


# Media-player states as plain strings (the exact values HA expects) — avoids a
# hard dependency on the MediaPlayerState enum, which also moved across builds.
#
# The matrix reports *power/connection* per port (`inactive` for sources,
# `allconnect` for sinks) but not active playback — it routes signals, it
# doesn't decode them. So the truest state we can advertise is:
#   port powered/connected  -> "on"
#   port powered off        -> "off"
# (`"playing"` would be a lie; `"on"` is the canonical HA state for
#  powered-but-not-playing-a-known-item.)
_STATE_ON = "on"
_STATE_OFF = "off"


def _dev(host: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, host)},
        name=f"Orei BK808 ({host})",
        manufacturer="Orei",
        model="BK808",
        configuration_url=f"https://{host}",
    )


# Static cover art, served by this integration's HomeAssistantView (see
# http_view.py) at <frontend>/local/orei_bk808/cover.jpg. A relative path
# always resolves against the frontend's own origin, so it works with or
# without an external/internal URL and behind any reverse proxy.
# Drop your own ``static/cover.jpg`` into the integration folder to swap it.
_COVER_URL = "/local/orei_bk808/cover.jpg"


# Module-level cache: the cover is read at most once per HA process and shared
# by every media player (16 total) via `async_get_media_image`.
_cover_cache: "tuple[bytes, str] | None" = None
_cover_cache_loaded = False


def _read_cover_sync() -> "tuple[bytes, str] | None":
    """Blocking read — always run via `asyncio.to_thread` from the event loop."""
    path = Path(__file__).parent / "static" / "cover.jpg"
    try:
        return (path.read_bytes(), "image/jpeg")
    except OSError as err:
        _LOGGER.warning("Could not read bundled cover art: %s", err)
        return None


async def _get_cover_bytes() -> "tuple[bytes, str] | None":
    """Return cached cover bytes, loading off the event loop on first hit."""
    global _cover_cache, _cover_cache_loaded
    if not _cover_cache_loaded:
        _cover_cache_loaded = True
        _cover_cache = await asyncio.to_thread(_read_cover_sync)
    return _cover_cache


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
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
        # A non-None media_image_url tells the frontend to request the image
        # (via media_player_proxy). The actual bytes are returned by our
        # async_get_media_image override below — no network fetch of self.
        self._attr_media_image_url = _COVER_URL

    async def async_get_media_image(self) -> "tuple[bytes | None, str | None]":
        """Return the bundled cover art directly to HA's media_player_proxy.

        The stock implementation (see homeassistant/components/media_player/__init__.py)
        re-fetches `media_image_url` over HTTP on the server side, which breaks
        behind a reverse proxy (the self-request can't round-trip to
        `ha.local.cbrpnk.pw`). Handing the proxy the bytes directly lets
        every media-control card show the cover with zero network dependency.
        Uses a module-level cache so the 472 KB file is read at most once
        per Home Assistant process, shared by all 16 players.
        """
        cov = _get_cover_bytes()
        if cov is None:
            return None, None
        return cov

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
        # Show the user-defined input name (falls back to "Input N") while keeping
        # a stable unique id. Entity id stays media_player.input_<N>-ish.
        self._attr_name = coordinator.input_display_name(port)
        self._attr_unique_id = f"{hostname}_input_{port}"

    @property
    def state(self) -> str | None:
        # The device reports whether the *source* on this input is powered/on
        # (`inactive`=1) but not playback — so "on" (powered) vs off. This is
        # what actually lights up the history; routing alone left every port
        # "idle" forever.
        return _STATE_ON if self.coordinator.input_is_on(self._port) else _STATE_OFF

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.input_is_on(self._port)

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
        # Show the user-defined output name (falls back to "Output N") while
        # keeping a stable unique id.
        self._attr_name = coordinator.output_display_name(port)
        self._attr_unique_id = f"{hostname}_output_{port}"

    @property
    def state(self) -> str | None:
        # The device reports whether the *sink* on this output is connected/on
        # (`allconnect`=1) but not playback — so "on" (powered) vs off, not routing.
        return _STATE_ON if self.coordinator.output_is_on(self._port) else _STATE_OFF

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.output_is_on(self._port)

    @property
    def source_list(self) -> list[str] | None:
        return [self.coordinator.input_display_name(i) for i in range(1, NUM_PORTS + 1)]

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
                _LOGGER.info("output %d select_source -> %s", self._port, source)
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
