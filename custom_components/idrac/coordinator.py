"""DataUpdateCoordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_CONNECTION_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_CONNECTION_TYPE,
    DOMAIN,
)
from .redfish.redfish_client import RedfishError
from .redfish.redfish_coordinator import RedfishCoordinator
from .snmp.snmp_coordinator import SNMPCoordinator

_LOGGER = logging.getLogger(__name__)


class IdracDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Dell iDRAC integration.
    
    This coordinator manages data collection from Dell iDRAC devices using
    either Redfish API, SNMP, or a hybrid approach. It delegates protocol-specific
    operations to specialized coordinators while providing a unified interface
    for the Home Assistant integration.
    
    Attributes:
        entry: The config entry for this coordinator.
        host: The iDRAC host address.
        connection_type: Type of connection (redfish, snmp, or hybrid).
        protocol_coordinator: Primary coordinator for data collection.
        snmp_coordinator: SNMP coordinator (hybrid mode only).
        redfish_coordinator: Redfish coordinator (hybrid mode only).
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Dell iDRAC data update coordinator.
        
        Args:
            hass: Home Assistant instance.
            entry: Configuration entry containing connection details.
        """
        _LOGGER.debug("Initializing IdracDataUpdateCoordinator")
        
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.connection_type = entry.data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        
        _LOGGER.debug("Host: %s, Connection type: %s", self.host, self.connection_type)
        
        # Initialize protocol-specific coordinators
        try:
            if self.connection_type == "redfish":
                _LOGGER.debug("Creating RedfishCoordinator for redfish mode")
                self.protocol_coordinator = RedfishCoordinator(hass, entry)
            elif self.connection_type == "hybrid":
                # Hybrid mode: SNMP for data, Redfish for controls
                _LOGGER.debug("Creating coordinators for hybrid mode")
                _LOGGER.debug("Creating SNMPCoordinator")
                self.snmp_coordinator = SNMPCoordinator(hass, entry)
                _LOGGER.debug("Creating RedfishCoordinator")
                self.redfish_coordinator = RedfishCoordinator(hass, entry)
                self.protocol_coordinator = self.snmp_coordinator  # Primary data source
                _LOGGER.debug("Hybrid mode coordinators created successfully")
            else:
                # SNMP only
                _LOGGER.debug("Creating SNMPCoordinator for snmp mode")
                self.protocol_coordinator = SNMPCoordinator(hass, entry)
            
            _LOGGER.debug("Protocol coordinators created successfully")
        except Exception as exc:
            _LOGGER.error("Failed to create protocol coordinators: %s", exc, exc_info=True)
            raise
        
        # Store server identification for logging
        port = self.entry.data.get('port', 'unknown')
        if isinstance(port, (int, float)):
            port = int(port)
        self._server_id = f"{self.host}:{port}"
        
        _LOGGER.debug("Server ID: %s", self._server_id)
        
        # System identification data for device info
        self._device_info = None

        # Get scan interval from options first, then config data, then default
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        _LOGGER.debug("Scan interval: %d seconds", scan_interval)
        
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=DOMAIN,
                update_interval=timedelta(seconds=scan_interval),
            )
            _LOGGER.debug("DataUpdateCoordinator parent initialized successfully")
        except Exception as exc:
            _LOGGER.error("Failed to initialize DataUpdateCoordinator parent: %s", exc, exc_info=True)
            raise

    async def _async_fetch_device_info(self) -> dict[str, Any]:
        """Fetch device information for device registry.
        
        This method retrieves basic device information like model, serial number,
        and BIOS version to populate the device registry in Home Assistant.
        The information is cached after the first successful fetch.
        
        Returns:
            Dictionary containing device information for the registry.
        """
        if self._device_info is not None:
            return self._device_info
        
        # Get device info from the primary protocol coordinator (cached after first fetch)
        device_info = await self.protocol_coordinator.get_device_info()
        
        self._device_info = device_info
        return device_info

    @property 
    def device_info(self) -> dict[str, Any]:
        """Return device information for Home Assistant device registry.
        
        Provides device information used by Home Assistant to create and
        identify the device in the device registry. Falls back to basic
        iDRAC information if detailed device info hasn't been fetched yet.
        
        Returns:
            Dictionary containing device identifiers and metadata.
        """
        return self._device_info or {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Dell iDRAC ({self.host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{self.host}" if self.connection_type == "redfish" else None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the Dell iDRAC device.
        
        This method is called by Home Assistant's DataUpdateCoordinator at regular
        intervals. It delegates the actual data collection to the appropriate
        protocol-specific coordinator based on the connection type.
        
        Returns:
            Dictionary containing all sensor data and device status information.
            
        Raises:
            UpdateFailed: If data collection fails for any reason.
        """
        try:
            # Fetch device info on first run
            if self._device_info is None:
                _LOGGER.debug("Fetching device information for %s", self._server_id)
                await self._async_fetch_device_info()
                _LOGGER.info("Connected to %s: %s", 
                           self._device_info.get("name", "Unknown Device"),
                           f"{self._device_info.get('model', 'Unknown Model')} "
                           f"(Serial: {self._device_info.get('serial_number', 'Unknown')})")
            
            # Get sensor data from protocol coordinator
            _LOGGER.debug("Updating sensor data via %s protocol", self.connection_type)
            data = await self.protocol_coordinator.get_sensor_data()
            
            # In hybrid mode, LED state will be fetched on-demand by the switch entity
            # This avoids slow Redfish calls during regular sensor updates
            
            return data

        except RedfishError as exc:
            _LOGGER.error("Redfish authentication failed for iDRAC %s: %s", self._server_id, exc)
            raise UpdateFailed(f"Authentication failed for iDRAC {self._server_id}: {exc}") from exc
        except TimeoutError as exc:
            _LOGGER.warning("Timeout communicating with iDRAC %s: %s", self._server_id, exc)
            raise UpdateFailed(f"Timeout communicating with iDRAC {self._server_id}") from exc
        except ConnectionError as exc:
            _LOGGER.warning("Connection error with iDRAC %s: %s", self._server_id, exc)
            raise UpdateFailed(f"Connection error with iDRAC {self._server_id}") from exc
        except Exception as exc:
            _LOGGER.error("Unexpected error communicating with iDRAC %s (%s mode): %s", 
                         self._server_id, self.connection_type, exc)
            raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc

    async def async_reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset the Dell server system via Redfish API.
        
        This method sends a reset command to the server. Only available when
        using Redfish API or hybrid connection modes.
        
        Args:
            reset_type: Type of reset to perform. Common values include:
                - "GracefulRestart": Graceful restart (default)
                - "ForceRestart": Force restart
                - "PowerCycle": Power cycle
                
        Returns:
            True if reset command was sent successfully, False otherwise.
        """
        if self.connection_type not in ["redfish", "hybrid"]:
            _LOGGER.error("System reset only available via Redfish API or hybrid mode")
            return False
        
        # Use Redfish coordinator for system reset
        try:
            if self.connection_type == "hybrid":
                result = await self.redfish_coordinator.reset_system(reset_type)
            else:
                result = await self.protocol_coordinator.reset_system(reset_type)
            
            if result:
                _LOGGER.info("Successfully sent %s command to iDRAC %s", reset_type, self._server_id)
            else:
                _LOGGER.warning("Failed to send %s command to iDRAC %s", reset_type, self._server_id)
            
            return result
        except Exception as exc:
            _LOGGER.error("Error sending reset command to iDRAC %s: %s", self._server_id, exc)
            return False

    async def async_set_indicator_led(self, state: str) -> bool:
        """Set the server's indicator LED state via Redfish API.
        
        Controls the server's front panel indicator LED. Only available when
        using Redfish API or hybrid connection modes.
        
        Args:
            state: LED state to set. Common values include:
                - "Lit": Turn LED on
                - "Blinking": Make LED blink
                - "Off": Turn LED off
                
        Returns:
            True if LED state was set successfully, False otherwise.
        """
        if self.connection_type not in ["redfish", "hybrid"]:
            _LOGGER.error("LED control only available via Redfish API or hybrid mode")
            return False
        
        # Use Redfish coordinator for LED control
        try:
            if self.connection_type == "hybrid":
                result = await self.redfish_coordinator.set_indicator_led(state)
            else:
                result = await self.protocol_coordinator.set_indicator_led(state)
            
            if result:
                _LOGGER.info("Successfully set LED to %s on iDRAC %s", state, self._server_id)
            else:
                _LOGGER.warning("Failed to set LED to %s on iDRAC %s", state, self._server_id)
            
            return result
        except Exception as exc:
            _LOGGER.error("Error setting LED state on iDRAC %s: %s", self._server_id, exc)
            return False

    async def async_set_snmp_value(self, oid: str, value: int) -> bool:
        """Set an SNMP value via the appropriate coordinator.
        
        This method provides a unified interface for SNMP SET operations
        regardless of the connection type.
        
        Args:
            oid: SNMP OID to set
            value: Integer value to set
            
        Returns:
            True if the operation was successful, False otherwise.
        """
        if self.connection_type not in ["snmp", "hybrid"]:
            _LOGGER.error("SNMP operations only available in SNMP or hybrid connection modes")
            return False
        
        try:
            # Use SNMP coordinator for SNMP operations
            if self.connection_type == "hybrid":
                return await self.snmp_coordinator.set_snmp_value(oid, value)
            else:
                return await self.protocol_coordinator.set_snmp_value(oid, value)
                
        except Exception as exc:
            _LOGGER.error("Error setting SNMP value for OID %s: %s", oid, exc)
            return False

    async def async_get_snmp_value(self, oid: str) -> int | None:
        """Get an SNMP value via the appropriate coordinator.
        
        This method provides a unified interface for SNMP GET operations
        regardless of the connection type.
        
        Args:
            oid: SNMP OID to get
            
        Returns:
            Integer value if successful, None otherwise.
        """
        if self.connection_type not in ["snmp", "hybrid"]:
            _LOGGER.error("SNMP operations only available in SNMP or hybrid connection modes")
            return None
        
        try:
            # Use SNMP coordinator for SNMP operations
            if self.connection_type == "hybrid":
                return await self.snmp_coordinator.get_snmp_value(oid)
            else:
                return await self.protocol_coordinator.get_snmp_value(oid)
                
        except Exception as exc:
            _LOGGER.error("Error getting SNMP value for OID %s: %s", oid, exc)
            return None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close all connections.
        
        This method is called when Home Assistant is shutting down or when
        the integration is being unloaded. It ensures all network connections
        are properly closed to prevent resource leaks.
        """
        await self.protocol_coordinator.close()
        
        if self.connection_type == "hybrid" and hasattr(self, 'redfish_coordinator'):
            await self.redfish_coordinator.close()