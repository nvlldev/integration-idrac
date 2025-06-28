"""Utility functions for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from .coordinator_snmp import SNMPDataUpdateCoordinator
    from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def get_device_name_prefix(coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator) -> str:
    """Get device name prefix for entity naming."""
    # For now, use basic prefix since we don't have sync device_info access
    # This matches the original pattern but is simplified for the new coordinators
    return f"Dell iDRAC ({coordinator.host})"


def get_coordinators(hass: HomeAssistant, config_entry: ConfigEntry) -> dict[str, SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator]:
    """Get SNMP and Redfish coordinators from hass data."""
    from .const import DOMAIN
    return hass.data[DOMAIN][config_entry.entry_id]


def get_coordinator_pair(hass: HomeAssistant, config_entry: ConfigEntry) -> tuple[SNMPDataUpdateCoordinator, RedfishDataUpdateCoordinator]:
    """Get SNMP and Redfish coordinators as a tuple for easy unpacking."""
    coordinators = get_coordinators(hass, config_entry)
    return coordinators["snmp"], coordinators["redfish"]


def validate_coordinator_data(coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, category: str) -> bool:
    """Validate that coordinator has data for the specified category."""
    if not coordinator:
        return False
    if not coordinator.data:
        return False
    if category not in coordinator.data:
        return False
    return bool(coordinator.data[category])


def get_fallback_device_info(host: str) -> dict[str, any]:
    """Get fallback device info when coordinator device info is unavailable."""
    return {
        "identifiers": {("idrac", host)},
        "name": f"Dell iDRAC ({host})",
        "manufacturer": "Dell",
        "model": "iDRAC",
        "configuration_url": f"https://{host}",
    }


def map_dell_status(status_value: int | str | None, status_type: str = "health") -> str | None:
    """Map Dell iDRAC status values to human-readable strings.
    
    Args:
        status_value: The status value from SNMP or Redfish
        status_type: Type of status mapping ("health", "temperature", "intrusion")
        
    Returns:
        Human-readable status string or None if invalid
    """
    from .const import DELL_HEALTH_STATUS, DELL_TEMPERATURE_STATUS, DELL_INTRUSION_STATUS
    
    if status_value is None:
        return None
    
    # Handle string status values (typically from Redfish)
    if isinstance(status_value, str):
        return status_value.lower()
    
    # Handle numeric status values (typically from SNMP)
    try:
        status_int = int(status_value)
        if status_type == "temperature":
            return DELL_TEMPERATURE_STATUS.get(status_int, "unknown")
        elif status_type == "intrusion":
            return DELL_INTRUSION_STATUS.get(status_int, "unknown")
        else:  # Default to health status
            return DELL_HEALTH_STATUS.get(status_int, "unknown")
    except (ValueError, TypeError):
        return "unknown"


def format_oid_with_index(oid_template: str, index: int | str) -> str:
    """Format an OID template with an index value using f-string style.
    
    Args:
        oid_template: OID template with {index} placeholder
        index: Index value to substitute
        
    Returns:
        Formatted OID string
    """
    return oid_template.replace("{index}", str(index))