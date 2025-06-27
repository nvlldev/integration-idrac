"""The Dell iDRAC integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IdracDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,    # Re-enabled for Redfish LED control
    Platform.BUTTON,    # Re-enabled for Redfish power control
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dell iDRAC from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = IdracDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this is the last iDRAC integration
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "refresh_sensors")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Dell iDRAC integration."""
    
    async def async_refresh_sensors(call: ServiceCall) -> None:
        """Refresh discovered sensors for all iDRAC integrations."""
        _LOGGER.info("Refreshing sensors for all Dell iDRAC integrations")
        
        # Get all iDRAC config entries
        entries = [
            entry for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state.recoverable
        ]
        
        if not entries:
            _LOGGER.warning("No Dell iDRAC integrations found")
            return
        
        for entry in entries:
            _LOGGER.info("Refreshing sensors for iDRAC: %s", entry.title)
            try:
                # Reload the entire entry to trigger sensor discovery
                await hass.config_entries.async_reload(entry.entry_id)
            except Exception as exc:
                _LOGGER.error("Failed to refresh sensors for %s: %s", entry.title, exc)
        
        _LOGGER.info("Sensor refresh completed for %d iDRAC integration(s)", len(entries))

    # Register the service if it doesn't already exist
    if not hass.services.has_service(DOMAIN, "refresh_sensors"):
        hass.services.async_register(
            DOMAIN,
            "refresh_sensors",
            async_refresh_sensors,
            schema=vol.Schema({}),
        )