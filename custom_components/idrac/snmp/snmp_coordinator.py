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
        _LOGGER.debug("Initializing SNMPCoordinator")
        
        self.hass = hass
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get("port")
        
        _LOGGER.debug("SNMP coordinator host: %s, port: %s", self.host, self.port)
        
        # Create SNMP client with error handling
        try:
            _LOGGER.debug("Creating SNMPClient")
            self.client = SNMPClient(entry)
            _LOGGER.debug("SNMPClient created successfully")
        except Exception as exc:
            _LOGGER.error("Failed to create SNMPClient: %s", exc, exc_info=True)
            raise
        
        # Store server identification for logging
        port = self.port
        if isinstance(port, (int, float)):
            port = int(port)
        self._server_id = f"{self.host}:{port}"
        
        _LOGGER.debug("SNMP coordinator server ID: %s", self._server_id)
        
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
        
        # Get device info via SNMP client with explicit error handling
        try:
            _LOGGER.debug("Calling SNMP client get_device_info()")
            snmp_device_info = await self.client.get_device_info()
            _LOGGER.debug("SNMP client returned device info: %s", snmp_device_info)
            device_info.update(snmp_device_info)
        except Exception as exc:
            _LOGGER.error("Error getting device info from SNMP client: %s", exc, exc_info=True)
            # Continue with basic device info
        
        self._device_info = device_info
        _LOGGER.debug("Final device info: %s", device_info)
        return device_info

    async def get_sensor_data(self) -> dict[str, Any]:
        """Get sensor data via SNMP.
        
        Delegates sensor data collection to the SNMP client and returns
        the organized sensor data dictionary.
        
        Returns:
            Dictionary containing all available sensor data from the iDRAC.
        """
        return await self.client.get_sensor_data()

    async def set_snmp_value(self, oid: str, value: int) -> bool:
        """Set an SNMP value via the SNMP client.
        
        Args:
            oid: SNMP OID to set
            value: Integer value to set
            
        Returns:
            True if the operation was successful, False otherwise.
        """
        return await self.client.set_snmp_value(oid, value)

    async def get_snmp_value(self, oid: str) -> int | None:
        """Get an SNMP value via the SNMP client.
        
        Args:
            oid: SNMP OID to get
            
        Returns:
            Integer value if successful, None otherwise.
        """
        return await self.client.get_value(oid)

    async def reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset the server system.
        
        SNMP does not support system reset operations.
        This method always returns False and logs a warning.
        
        Args:
            reset_type: Type of reset (ignored for SNMP)
            
        Returns:
            False - SNMP does not support this operation
        """
        _LOGGER.warning("System reset not supported via SNMP - use Redfish or hybrid mode")
        return False

    async def set_indicator_led(self, state: str) -> bool:
        """Set the server's indicator LED state.
        
        SNMP does not support LED control operations.
        This method always returns False and logs a warning.
        
        Args:
            state: LED state (ignored for SNMP)
            
        Returns:
            False - SNMP does not support this operation
        """
        _LOGGER.warning("LED control not supported via SNMP - use Redfish or hybrid mode")
        return False

    async def close(self) -> None:
        """Close the coordinator.
        
        Cleanup method called when the coordinator is being shut down.
        SNMP doesn't require explicit connection cleanup, but this method
        is provided for consistency with the coordinator interface.
        """
        # SNMP client doesn't need explicit closing, but keep for consistency
        pass