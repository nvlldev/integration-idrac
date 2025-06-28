"""SNMP-only Data Update Coordinator for Dell iDRAC integration."""
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
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .snmp.snmp_coordinator import SNMPCoordinator

_LOGGER = logging.getLogger(__name__)


class SNMPDataUpdateCoordinator(DataUpdateCoordinator):
    """SNMP-only data update coordinator for Dell iDRAC.
    
    This coordinator handles only SNMP data collection, allowing it to update
    on its own schedule independent of Redfish data collection.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, scan_interval: int | None = None) -> None:
        """Initialize the SNMP coordinator."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        
        # Use provided scan interval or get from options/config/default
        if scan_interval is None:
            scan_interval = entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )

        _LOGGER.debug("SNMP coordinator for %s with %ds update interval", self.host, scan_interval)
        
        # Create SNMP coordinator
        try:
            self.snmp_coordinator = SNMPCoordinator(hass, entry)
            _LOGGER.debug("SNMP coordinator created successfully")
        except Exception as exc:
            _LOGGER.error("Failed to create SNMP coordinator: %s", exc, exc_info=True)
            raise

        # Store server identification for logging
        self._server_id = f"{self.host}:snmp"

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_snmp_{self.host}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch SNMP data from the Dell iDRAC device.
        
        Returns:
            Dictionary containing SNMP sensor data.
            
        Raises:
            UpdateFailed: If SNMP data collection fails.
        """
        _LOGGER.debug("Starting SNMP data collection for %s", self._server_id)
        
        try:
            # Get SNMP sensor data
            snmp_data = await self.snmp_coordinator.get_sensor_data()
            
            _LOGGER.debug("SNMP data collection completed for %s: %d categories", 
                         self._server_id, len(snmp_data))
            
            return snmp_data
            
        except Exception as exc:
            _LOGGER.error("SNMP data collection failed for %s: %s", self._server_id, exc)
            raise UpdateFailed(f"Failed to fetch SNMP data: {exc}") from exc

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information via SNMP."""
        return await self.snmp_coordinator.get_device_info()