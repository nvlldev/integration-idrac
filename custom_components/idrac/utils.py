"""Utility functions for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator_snmp import SNMPDataUpdateCoordinator
    from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def get_device_name_prefix(coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator) -> str:
    """Get device name prefix for entity naming."""
    # For now, use basic prefix since we don't have sync device_info access
    # This matches the original pattern but is simplified for the new coordinators
    return f"Dell iDRAC ({coordinator.host})"