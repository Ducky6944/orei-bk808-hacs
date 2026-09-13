"""Core initialization for Orei BK808 integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import OreiCoordinator
from .const import (
    DOMAIN, CONF_HOST,
    CONF_INPUT_NAMES, CONF_OUTPUT_NAMES,
    DEFAULT_INPUT_NAMES, DEFAULT_OUTPUT_NAMES,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Orei BK808 from a config entry."""

    host = entry.data[CONF_HOST]
    input_names = entry.data.get(CONF_INPUT_NAMES, DEFAULT_INPUT_NAMES)
    output_names = entry.data.get(CONF_OUTPUT_NAMES, DEFAULT_OUTPUT_NAMES)

    coordinator = OreiCoordinator(
        hass=hass,
        host=host,
        input_names=input_names,
        output_names=output_names,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to matrix at {host}"
        ) from ex

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Orei BK808 matrix at %s set up successfully", host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
