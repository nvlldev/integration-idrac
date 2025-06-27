"""SNMP protocol coordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .snmp_client import SNMPClient
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SNMPCoordinator:
    """SNMP protocol coordinator for Dell iDRAC.
    
    This coordinator manages SNMP-based data collection from Dell iDRAC devices.
    It provides a consistent interface for sensor data retrieval and device
    information while delegating the actual SNMP operations to the SNMPClient.
    
    The coordinator supports:
    - Device information retrieval via SNMP
    - Comprehensive sensor data collection
    - Graceful error handling and logging
    
    Attributes:
        hass: Home Assistant instance.
        entry: Configuration entry.
        host: iDRAC host address.
        client: SNMP client instance.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the SNMP coordinator.
        
        Args:
            hass: Home Assistant instance.
            entry: Configuration entry containing SNMP connection details.
        """
        self.hass = hass
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get("port")
        
        # Create SNMP client  
        self.client = SNMPClient(entry)
        
        # Store server identification for logging
        port = self.port
        if isinstance(port, (int, float)):
            port = int(port)
        self._server_id = f"{self.host}:{port}"
        
        # System identification data for device info
        self._device_info = None

    async def get_device_info(self) -> dict[str, Any]:
        """Fetch device information for device registry via SNMP.
        
        Retrieves device information using SNMP and caches it for subsequent calls.
        The information is used to populate the Home Assistant device registry.
        
        Returns:
            Dictionary containing device information including identifiers,
            manufacturer, model, and name.
        """
        if self._device_info is not None:
            return self._device_info
        
        _LOGGER.debug("Fetching SNMP device info for %s", self._server_id)
        
        device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "manufacturer": "Dell",
        }
        
        # Get device info via SNMP client
        snmp_device_info = await self.client.get_device_info()
        device_info.update(snmp_device_info)
        
        self._device_info = device_info
        _LOGGER.debug("Device info: %s", device_info)
        return device_info

    async def get_sensor_data(self) -> dict[str, Any]:
        """Get sensor data via SNMP.
        
        Delegates sensor data collection to the SNMP client and returns
        the organized sensor data dictionary.
        
        Returns:
            Dictionary containing all available sensor data from the iDRAC.
        """
        return await self.client.get_sensor_data()

    async def close(self) -> None:
        """Close the coordinator.
        
        Cleanup method called when the coordinator is being shut down.
        SNMP doesn't require explicit connection cleanup, but this method
        is provided for consistency with the coordinator interface.
        """
        # SNMP client doesn't need explicit closing, but keep for consistency
        pass