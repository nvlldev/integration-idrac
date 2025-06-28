"""Redfish-only Data Update Coordinator for Dell iDRAC integration."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .redfish.redfish_coordinator import RedfishCoordinator

_LOGGER = logging.getLogger(__name__)


class RedfishDataUpdateCoordinator(DataUpdateCoordinator):
    """Redfish-only data update coordinator for Dell iDRAC.
    
    This coordinator handles only Redfish data collection, allowing it to update
    on its own schedule independent of SNMP data collection.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, scan_interval: int | None = None) -> None:
        """Initialize the Redfish coordinator."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        
        # Use provided scan interval or get from options/config/default
        if scan_interval is None:
            scan_interval = entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )

        _LOGGER.debug("Redfish coordinator for %s with %ds update interval", self.host, scan_interval)
        
        # Create Redfish coordinator
        try:
            self.redfish_coordinator = RedfishCoordinator(hass, entry)
            _LOGGER.debug("Redfish coordinator created successfully")
        except Exception as exc:
            _LOGGER.error("Failed to create Redfish coordinator: %s", exc, exc_info=True)
            raise

        # Store server identification for logging
        self._server_id = f"{self.host}:redfish"

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_redfish_{self.host}",
            update_interval=timedelta(seconds=scan_interval),
        )
        
        # Track update duration
        self.last_update_duration = None
    
    @property
    def connection_type(self) -> str:
        """Return the connection type."""
        return "redfish"

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch Redfish data from the Dell iDRAC device.
        
        Returns:
            Dictionary containing Redfish sensor data.
            
        Raises:
            UpdateFailed: If Redfish data collection fails.
        """
        start_time = time.time()
        _LOGGER.debug("Starting Redfish data collection for %s", self._server_id)
        
        try:
            # Get Redfish sensor data
            redfish_data = await self.redfish_coordinator.get_sensor_data()
            
            # Track update duration
            self.last_update_duration = round(time.time() - start_time, 3)
            
            _LOGGER.debug("Redfish data collection completed for %s: %d categories in %.3fs", 
                         self._server_id, len(redfish_data), self.last_update_duration)
            
            return redfish_data
            
        except Exception as exc:
            # Track duration even on failure
            self.last_update_duration = round(time.time() - start_time, 3)
            _LOGGER.error("Redfish data collection failed for %s: %s (%.3fs)", 
                         self._server_id, exc, self.last_update_duration)
            raise UpdateFailed(f"Failed to fetch Redfish data: {exc}") from exc

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information via Redfish."""
        return await self.redfish_coordinator.get_device_info()
        
    async def reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset system via Redfish."""
        return await self.redfish_coordinator.reset_system(reset_type)
        
    async def set_indicator_led(self, state: str) -> bool:
        """Set indicator LED via Redfish."""
        return await self.redfish_coordinator.set_indicator_led(state)
        
    async def async_set_indicator_led(self, state: str) -> bool:
        """Set indicator LED via Redfish (async alias)."""
        return await self.set_indicator_led(state)
        
    async def async_reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset system via Redfish (async alias)."""
        return await self.reset_system(reset_type)
        
    async def async_set_snmp_value(self, oid: str, value: int) -> bool:
        """SNMP operations not available in Redfish-only mode."""
        _LOGGER.warning("SNMP operations not available in Redfish-only mode")
        return False
        
    async def async_get_snmp_value(self, oid: str) -> int | None:
        """SNMP operations not available in Redfish-only mode."""
        _LOGGER.warning("SNMP operations not available in Redfish-only mode")
        return None
        
