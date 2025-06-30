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

    # Create coordinators based on connection type
    connection_type = entry.data.get("connection_type", "hybrid")
    coordinators = {}
    
    try:
        # Always create SNMP coordinator for SNMP-capable modes
        if connection_type in ["snmp", "snmp_only", "hybrid"]:
            snmp_scan_interval = entry.options.get("snmp_scan_interval", entry.data.get("snmp_scan_interval", 15))  # Default 15s for SNMP
            from .coordinator_snmp import SNMPDataUpdateCoordinator
            snmp_coordinator = SNMPDataUpdateCoordinator(hass, entry, snmp_scan_interval)
            coordinators["snmp"] = snmp_coordinator
            _LOGGER.debug("Created SNMP coordinator with %ds update interval", snmp_scan_interval)
        
        # Create Redfish coordinator only for Redfish-capable modes (skip in SNMP-only mode)
        if connection_type in ["redfish", "hybrid"]:
            redfish_scan_interval = entry.options.get("redfish_scan_interval", entry.data.get("redfish_scan_interval", 45))  # Default 45s for Redfish
            from .coordinator_redfish import RedfishDataUpdateCoordinator
            redfish_coordinator = RedfishDataUpdateCoordinator(hass, entry, redfish_scan_interval)
            coordinators["redfish"] = redfish_coordinator
            _LOGGER.debug("Created Redfish coordinator with %ds update interval", redfish_scan_interval)
        
        _LOGGER.info("Connection mode: %s - Created %d coordinators", connection_type, len(coordinators))
        
    except Exception as exc:
        _LOGGER.error("Failed to create independent coordinators: %s", exc, exc_info=True)
        raise ConfigEntryNotReady from exc

    # Initialize coordinators
    try:
        import asyncio
        tasks = []
        
        # Create initialization tasks for available coordinators
        if "snmp" in coordinators:
            tasks.append(("snmp", asyncio.create_task(coordinators["snmp"].async_config_entry_first_refresh())))
        if "redfish" in coordinators:
            tasks.append(("redfish", asyncio.create_task(coordinators["redfish"].async_config_entry_first_refresh())))
        
        # Wait for coordinators with individual error handling
        coordinator_results = {}
        
        for coord_name, task in tasks:
            try:
                await task
                coordinator_results[coord_name] = coordinators[coord_name].last_update_success
            except Exception as exc:
                _LOGGER.warning("%s coordinator initialization failed: %s", coord_name.title(), exc)
                coordinator_results[coord_name] = False
            
        # Ensure at least one coordinator is working
        successful_coordinators = [name for name, success in coordinator_results.items() if success]
        if not successful_coordinators:
            failed_names = list(coordinator_results.keys())
            raise ConfigEntryNotReady(f"All coordinators failed to initialize: {', '.join(failed_names)}")
            
        # Log results
        status_parts = []
        for coord_name in ["snmp", "redfish"]:
            if coord_name in coordinator_results:
                status = "✓" if coordinator_results[coord_name] else "✗"
                status_parts.append(f"{coord_name.title()}: {status}")
                
        _LOGGER.info("Coordinators initialized - %s", ", ".join(status_parts))
            
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