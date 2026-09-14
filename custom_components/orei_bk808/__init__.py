"""Core setup for the Orei BK808 HDMI Matrix integration."""

import asyncio
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_INPUT_NAMES,
    CONF_OUTPUT_NAMES,
    DEFAULT_INPUT_NAMES,
    DEFAULT_OUTPUT_NAMES,
    NUM_PORTS,
    CEC_COMMAND_NAMES,
    PLATFORMS,
)
from .coordinator import OreiCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_INPUT = "input"
ATTR_OUTPUT = "output"
ATTR_PRESET = "preset"
ATTR_NAME = "name"
ATTR_SIDE = "side"
ATTR_PORT = "port"
ATTR_COMMAND = "command"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the domain (no-op for YAML)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_initial_refresh(
    coordinator: "OreiCoordinator",
    tries: int = 5,
    delay: float = 1.5,
) -> None:
    """First refresh with backoff.

    The BK808 has a sticky single connection; the *first* few requests after
    a cold boot can return a non-routing blob (or race the poller and return
    an empty body). A one-shot refresh therefore fails intermittently and
    logs "All state queries failed ... None". Retry a few times so a flaky
    cold start doesn't wedge the whole entry.
    """
    last: Optional[Exception] = None
    for i in range(tries):
        try:
            await coordinator.async_config_entry_first_refresh()
            return
        except ConfigEntryNotReady:
            raise
        except Exception as err:  # noqa: BLE001
            last = err
            _LOGGER.debug(
                "Initial refresh attempt %d/%d for %s failed: %s",
                i + 1, tries, coordinator.host, err,
            )
            if i < tries - 1:
                await asyncio.sleep(delay)
    raise last


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create the coordinator, register services, forward to platforms."""
    host = str(entry.data[CONF_HOST])
    input_names = entry.data.get(CONF_INPUT_NAMES, DEFAULT_INPUT_NAMES)
    output_names = entry.data.get(CONF_OUTPUT_NAMES, DEFAULT_OUTPUT_NAMES)

    coordinator = OreiCoordinator(
        hass=hass,
        host=host,
        input_names=input_names,
        output_names=output_names,
    )

    try:
        await async_initial_refresh(coordinator)
    except Exception as err:
        _LOGGER.error("Initial refresh failed for %s: %s", host, err)
        await coordinator.shutdown()
        raise ConfigEntryNotReady(f"Matrix at {host} is unreachable") from err

    hass.data[DOMAIN][entry.entry_id] = coordinator

    _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Orei BK808 matrix at %s set up", host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down the integration."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.shutdown()
    return ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload (called by the options flow)."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


# ------------------------------------------------------------------ services

_NUM_1_8 = vol.Range(min=1, max=NUM_PORTS)


def _register_services(hass: HomeAssistant) -> None:
    """Register all HA services for the matrix."""
    async def _route(call: ServiceCall) -> None:
        input_num = int(call.data[ATTR_INPUT])
        output_num = int(call.data[ATTR_OUTPUT])
        for entry_id, coord in hass.data[DOMAIN].items():
            await coord.set_route(output_num, input_num)

    async def _save_preset(call: ServiceCall) -> None:
        idx = int(call.data[ATTR_PRESET])
        for coord in hass.data[DOMAIN].values():
            await coord.save_preset(idx)

    async def _recall_preset(call: ServiceCall) -> None:
        idx = int(call.data[ATTR_PRESET])
        for coord in hass.data[DOMAIN].values():
            await coord.recall_preset(idx)

    async def _clear_preset(call: ServiceCall) -> None:
        idx = int(call.data[ATTR_PRESET])
        for coord in hass.data[DOMAIN].values():
            await coord.clear_preset(idx)

    async def _set_preset_name(call: ServiceCall) -> None:
        idx = int(call.data[ATTR_PRESET])
        name = str(call.data[ATTR_NAME])
        for coord in hass.data[DOMAIN].values():
            await coord.set_preset_name(idx, name)

    async def _cec(call: ServiceCall) -> None:
        side = str(call.data[ATTR_SIDE]).lower()
        port = int(call.data[ATTR_PORT])
        command = str(call.data[ATTR_COMMAND])
        if side not in ("input", "output"):
            raise ValueError(f"side must be input or output, got {side!r}")
        for coord in hass.data[DOMAIN].values():
            await coord.send_cec(side, port, command)

    async def _power(call: ServiceCall) -> None:
        on = bool(call.data.get("on", True))
        for coord in hass.data[DOMAIN].values():
            await coord.set_power(on)

    async def _mute(call: ServiceCall) -> None:
        out = int(call.data[ATTR_OUTPUT])
        muted = bool(call.data.get("muted", True))
        for coord in hass.data[DOMAIN].values():
            await coord.set_mute(out, muted)

    async def _refresh(_call: ServiceCall) -> None:
        for coord in hass.data[DOMAIN].values():
            await coord.async_request_refresh()

    async def _stop(_call: ServiceCall) -> None:
        pass

    services: dict = {
        "route": (
            vol.Schema(
                {
                    vol.Required(ATTR_INPUT): _NUM_1_8,
                    vol.Required(ATTR_OUTPUT): _NUM_1_8,
                }
            ),
            _route,
        ),
        "save_preset": (
            vol.Schema({vol.Required(ATTR_PRESET): _NUM_1_8}),
            _save_preset,
        ),
        "recall_preset": (
            vol.Schema({vol.Required(ATTR_PRESET): _NUM_1_8}),
            _recall_preset,
        ),
        "clear_preset": (
            vol.Schema({vol.Required(ATTR_PRESET): _NUM_1_8}),
            _clear_preset,
        ),
        "set_preset_name": (
            vol.Schema(
                {
                    vol.Required(ATTR_PRESET): _NUM_1_8,
                    vol.Required(ATTR_NAME): str,
                }
            ),
            _set_preset_name,
        ),
        "cec_command": (
            vol.Schema(
                {
                    vol.Required(ATTR_SIDE): vol.In(["input", "output"]),
                    vol.Required(ATTR_PORT): _NUM_1_8,
                    vol.Required(ATTR_COMMAND): vol.In(CEC_COMMAND_NAMES),
                }
            ),
            _cec,
        ),
        "set_power": (
            vol.Schema({vol.Optional("on", default=True): bool}),
            _power,
        ),
        "set_mute": (
            vol.Schema(
                {
                    vol.Required(ATTR_OUTPUT): _NUM_1_8,
                    vol.Optional("muted", default=True): bool,
                }
            ),
            _mute,
        ),
        "refresh": (vol.Schema({}), _refresh),
    }

    if "_orei_services_registered" in hass.data:
        return
    hass.data["_orei_services_registered"] = True

    for name, (schema, handler) in services.items():
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
