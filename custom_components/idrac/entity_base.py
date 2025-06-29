"""Base entity classes for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .utils import get_fallback_device_info

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from .coordinator_snmp import SNMPDataUpdateCoordinator
    from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IdracEntityBase(CoordinatorEntity):
    """Base class for all Dell iDRAC entities with common device info handling."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        entity_key: str,
        entity_name: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._entity_key = entity_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Set entity name without device prefix (new naming pattern)
        # Home Assistant will automatically combine device + entity names
        self._attr_name = entity_name
        self._attr_has_entity_name = True
        # Use stable unique_id based on integration domain, device_id and entity key
        # This ensures uniqueness across all integrations
        from .const import DOMAIN
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{entity_key}"

        # Store reference details for logging and device info
        self._host = host
        self._port = port
        self._config_entry = config_entry

        # Set device info immediately to ensure consistent entity ID generation
        self._attr_device_info = get_fallback_device_info(self.coordinator.host, port)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Set device info now that we can make async calls
        try:
            self._attr_device_info = await self.coordinator.get_device_info()
        except Exception as exc:
            _LOGGER.warning("Failed to get device info for %s: %s", self._entity_key, exc)
            # Provide fallback device info to ensure device is created
            self._attr_device_info = get_fallback_device_info(self.coordinator.host, self._port)

    @property
    def device_info(self):
        """Return device information."""
        # Always return device info - use fallback if not set
        if hasattr(self, '_attr_device_info') and self._attr_device_info:
            return self._attr_device_info
        
        # Fallback device info
        return get_fallback_device_info(self.coordinator.host, self._port)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success