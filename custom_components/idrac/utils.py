"""Utility functions for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator_snmp import SNMPDataUpdateCoordinator
    from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def get_device_name_prefix(coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator) -> str:
    """Get device name prefix for entity naming."""
    try:
        device_info = await coordinator.get_device_info()
        if device_info and "model" in device_info and device_info["model"] != "iDRAC":
            return f"Dell {device_info['model']} ({coordinator.host})"
        else:
            return f"Dell iDRAC ({coordinator.host})"
    except Exception:
        return f"Dell iDRAC ({coordinator.host})"