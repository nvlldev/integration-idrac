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
    a hybrid approach that combines Redfish API and SNMP for comprehensive
    sensor coverage. It supplements missing Redfish sensors with SNMP data
    to provide the most complete monitoring possible.
    
    Attributes:
        entry: The config entry for this coordinator.
        host: The iDRAC host address.
        snmp_coordinator: SNMP coordinator for sensor data.
        redfish_coordinator: Redfish coordinator for sensor data and controls.
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
        
        # Initialize both SNMP and Redfish coordinators for hybrid mode
        try:
            _LOGGER.debug("Creating coordinators for hybrid mode (SNMP + Redfish)")
            _LOGGER.debug("Creating SNMPCoordinator")
            self.snmp_coordinator = SNMPCoordinator(hass, entry)
            _LOGGER.debug("Creating RedfishCoordinator")
            self.redfish_coordinator = RedfishCoordinator(hass, entry)
            _LOGGER.debug("Hybrid mode coordinators created successfully")
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
        
        # Try Redfish first for device info, fallback to SNMP if needed
        try:
            device_info = await self.redfish_coordinator.get_device_info()
            self._device_info = device_info
            return device_info
        except Exception as exc:
            _LOGGER.debug("Redfish device info failed, trying SNMP: %s", exc)
            try:
                device_info = await self.snmp_coordinator.get_device_info()
                self._device_info = device_info
                return device_info
            except Exception as snmp_exc:
                _LOGGER.warning("Both Redfish and SNMP device info failed: %s, %s", exc, snmp_exc)
                # Return minimal device info
                device_info = {
                    "identifiers": {(DOMAIN, self._server_id)},
                    "name": f"Dell iDRAC ({self.host})",
                    "manufacturer": "Dell",
                    "model": "iDRAC",
                    "configuration_url": f"https://{self.host}",
                }
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
            "configuration_url": f"https://{self.host}",
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
            
            # Collect data from both sources in parallel for efficiency
            _LOGGER.debug("Updating sensor data via hybrid approach (Redfish + SNMP)")
            
            import asyncio
            
            # Start both data collection tasks concurrently
            redfish_task = self.redfish_coordinator.get_sensor_data()
            snmp_task = self.snmp_coordinator.get_sensor_data()
            
            # Wait for both with timeout
            try:
                redfish_data, snmp_data = await asyncio.wait_for(
                    asyncio.gather(redfish_task, snmp_task, return_exceptions=True),
                    timeout=60.0  # Total timeout for both sources
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Hybrid data collection timeout for %s, trying individual sources", self._server_id)
                # Fallback to individual collection with shorter timeouts
                redfish_data = await asyncio.wait_for(self.redfish_coordinator.get_sensor_data(), timeout=30.0)
                snmp_data = await asyncio.wait_for(self.snmp_coordinator.get_sensor_data(), timeout=30.0)
            
            # Handle exceptions from individual coordinators
            if isinstance(redfish_data, Exception):
                _LOGGER.warning("Redfish data collection failed: %s", redfish_data)
                redfish_data = {}
            if isinstance(snmp_data, Exception):
                _LOGGER.warning("SNMP data collection failed: %s", snmp_data)
                snmp_data = {}
            
            # Combine data sources - prefer Redfish, supplement with SNMP
            combined_data = self._combine_sensor_data(redfish_data, snmp_data)
            
            _LOGGER.debug("Hybrid data collection complete: %d Redfish fields, %d SNMP fields, %d combined fields",
                         len(redfish_data), len(snmp_data), len(combined_data))
            
            return combined_data

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

    def _combine_sensor_data(self, redfish_data: dict[str, Any], snmp_data: dict[str, Any]) -> dict[str, Any]:
        """Combine Redfish and SNMP sensor data, preferring Redfish when available.
        
        Args:
            redfish_data: Data from Redfish API
            snmp_data: Data from SNMP
            
        Returns:
            Combined sensor data dictionary
        """
        combined = dict(redfish_data)  # Start with Redfish data
        
        # Supplement with SNMP data for missing or incomplete sensors
        snmp_supplements = [
            # Chassis intrusion - often missing in Redfish
            ("chassis_intrusion", "system_intrusion"),
            # Memory health - may have more detail in SNMP
            ("memory_health", "memory"),
            # Storage components - often SNMP-only
            ("virtual_disks", "virtual_disks"),
            ("physical_disks", "physical_disks"),
            ("storage_controllers", "storage_controllers"),
            # Additional SNMP-only sensors
            ("detailed_memory", "detailed_memory"),
            ("system_voltages", "system_voltages"),
            ("power_consumption", "power_consumption"),
            ("system_intrusion", "system_intrusion"),
            ("system_battery", "system_battery"),
            ("processors", "processors"),
            ("psu_redundancy", "psu_redundancy"),
            ("system_health", "system_health"),
        ]
        
        for combined_key, snmp_key in snmp_supplements:
            if snmp_key in snmp_data:
                if combined_key not in combined or not combined[combined_key]:
                    # Use SNMP data if Redfish data is missing or empty
                    combined[combined_key] = snmp_data[snmp_key]
                    _LOGGER.debug("Supplemented %s with SNMP data", combined_key)
                elif combined_key == "chassis_intrusion" and combined[combined_key].get("status") == "Unknown":
                    # Special case: if Redfish intrusion is "Unknown", try SNMP
                    snmp_intrusion = snmp_data.get(snmp_key)
                    if snmp_intrusion is not None:
                        # Convert SNMP intrusion format to Redfish-like format
                        try:
                            intrusion_int = int(snmp_intrusion)
                            if intrusion_int == 1:
                                status = "Normal"
                            elif intrusion_int == 3:
                                status = "HardwareIntrusion"
                            else:
                                status = "Unknown"
                            
                            combined[combined_key] = {
                                "status": status,
                                "sensor_number": None,
                                "re_arm": None,
                                "source": "snmp"
                            }
                            _LOGGER.debug("Supplemented chassis intrusion with SNMP data: %s", status)
                        except (ValueError, TypeError):
                            pass
        
        return combined

    async def async_reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset the Dell server system via Redfish API.
        
        This method sends a reset command to the server using the Redfish coordinator.
        
        Args:
            reset_type: Type of reset to perform. Common values include:
                - "GracefulRestart": Graceful restart (default)
                - "ForceRestart": Force restart
                - "PowerCycle": Power cycle
                
        Returns:
            True if reset command was sent successfully, False otherwise.
        """
        # Use Redfish coordinator for system reset
        try:
            result = await self.redfish_coordinator.reset_system(reset_type)
            
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
        
        Controls the server's front panel indicator LED using the Redfish coordinator.
        
        Args:
            state: LED state to set. Common values include:
                - "Lit": Turn LED on
                - "Blinking": Make LED blink
                - "Off": Turn LED off
                
        Returns:
            True if LED state was set successfully, False otherwise.
        """
        # Use Redfish coordinator for LED control
        try:
            result = await self.redfish_coordinator.set_indicator_led(state)
            
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
        try:
            # Use SNMP coordinator for SNMP operations
            return await self.snmp_coordinator.set_snmp_value(oid, value)
                
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
        try:
            # Use SNMP coordinator for SNMP operations
            return await self.snmp_coordinator.get_snmp_value(oid)
                
        except Exception as exc:
            _LOGGER.error("Error getting SNMP value for OID %s: %s", oid, exc)
            return None

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close all connections.
        
        This method is called when Home Assistant is shutting down or when
        the integration is being unloaded. It ensures all network connections
        are properly closed to prevent resource leaks.
        """
        # Close both coordinators in hybrid mode
        await self.snmp_coordinator.close()
        await self.redfish_coordinator.close()