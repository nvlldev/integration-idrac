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