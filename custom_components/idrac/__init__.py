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

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,    # Re-enabled for Redfish LED control
    Platform.BUTTON,    # Re-enabled for Redfish power control
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dell iDRAC from a config entry."""
    _LOGGER.info("Setting up Dell iDRAC integration for %s", entry.title)
    
    hass.data.setdefault(DOMAIN, {})

    # Create independent coordinators for SNMP and Redfish
    # This allows each protocol to update on its own schedule and fail independently
    coordinators = {}
    
    try:
        # Create SNMP coordinator with faster update interval (SNMP is typically fast)
        snmp_scan_interval = entry.options.get("snmp_scan_interval", entry.data.get("snmp_scan_interval", 15))  # Default 15s for SNMP
        from .coordinator_snmp import SNMPDataUpdateCoordinator
        snmp_coordinator = SNMPDataUpdateCoordinator(hass, entry, snmp_scan_interval)
        coordinators["snmp"] = snmp_coordinator
        
        # Create Redfish coordinator with standard update interval  
        redfish_scan_interval = entry.options.get("redfish_scan_interval", entry.data.get("redfish_scan_interval", 45))  # Default 45s for Redfish
        from .coordinator_redfish import RedfishDataUpdateCoordinator
        redfish_coordinator = RedfishDataUpdateCoordinator(hass, entry, redfish_scan_interval)
        coordinators["redfish"] = redfish_coordinator
        
        _LOGGER.debug("Created coordinators - SNMP: %ds, Redfish: %ds", snmp_scan_interval, redfish_scan_interval)
        
    except Exception as exc:
        _LOGGER.error("Failed to create independent coordinators: %s", exc, exc_info=True)
        raise ConfigEntryNotReady from exc

    # Initialize both coordinators
    try:
        # Start both coordinators in parallel but don't fail if one fails
        import asyncio
        snmp_task = asyncio.create_task(coordinators["snmp"].async_config_entry_first_refresh())
        redfish_task = asyncio.create_task(coordinators["redfish"].async_config_entry_first_refresh())
        
        # Wait for both with individual error handling
        snmp_success = False
        redfish_success = False
        
        try:
            await snmp_task
            snmp_success = coordinators["snmp"].last_update_success
        except Exception as exc:
            _LOGGER.warning("SNMP coordinator initialization failed: %s", exc)
            
        try:
            await redfish_task  
            redfish_success = coordinators["redfish"].last_update_success
        except Exception as exc:
            _LOGGER.warning("Redfish coordinator initialization failed: %s", exc)
            
        # Ensure at least one coordinator is working
        if not snmp_success and not redfish_success:
            raise ConfigEntryNotReady("Both SNMP and Redfish coordinators failed to initialize")
            
        _LOGGER.info("Coordinators initialized - SNMP: %s, Redfish: %s", 
                    "✓" if snmp_success else "✗", "✓" if redfish_success else "✗")
            
    except ConfigEntryNotReady:
        raise
    except Exception as exc:
        _LOGGER.error("Failed during coordinator initialization: %s", exc, exc_info=True)
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][entry.entry_id] = coordinators

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as exc:
        _LOGGER.error("Failed to setup platforms: %s", exc, exc_info=True)
        raise

    # Register services
    try:
        await async_setup_services(hass)
    except Exception as exc:
        _LOGGER.error("Failed to setup services: %s", exc, exc_info=True)
        # Don't fail setup for service registration issues

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Dell iDRAC integration setup completed for %s", entry.title)
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