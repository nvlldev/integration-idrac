"""Binary sensor platform for Dell iDRAC integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DISCOVERED_PSUS, DOMAIN
from .coordinator import IdracDataUpdateCoordinator


def _to_snake_case(text: str) -> str:
    """Convert text to snake_case for entity ID compatibility."""
    import re
    # Replace spaces and special characters with underscores
    snake = re.sub(r'[^a-zA-Z0-9]', '_', text.lower())
    # Remove multiple underscores
    snake = re.sub(r'_+', '_', snake)
    # Remove leading/trailing underscores
    return snake.strip('_')


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC binary sensors."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracBinarySensor] = []

    # Add PSU status binary sensors
    for psu_index in config_entry.data.get(CONF_DISCOVERED_PSUS, []):
        entities.append(
            IdracPsuStatusBinarySensor(coordinator, config_entry, psu_index)
        )

    async_add_entities(entities)


class IdracBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Dell iDRAC binary sensors."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        self._attr_name = sensor_name
        # Use device name prefix for auto-rename compatibility
        device_name = f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})"
        device_snake = _to_snake_case(device_name)
        self._attr_unique_id = f"{device_snake}_{sensor_key}"
        self._attr_device_class = device_class

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{host}",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.is_on is not None


class IdracPsuStatusBinarySensor(IdracBinarySensor):
    """Dell iDRAC PSU status binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        psu_index: int,
    ) -> None:
        """Initialize the PSU status binary sensor."""
        sensor_key = f"psu_status_{psu_index}"
        sensor_name = f"PSU {psu_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )
        # Override the unique_id for auto-rename compatibility  
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_name = f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})"
        device_snake = _to_snake_case(device_name)
        self._attr_unique_id = f"{device_snake}_psu_{psu_index}_status"

    @property
    def is_on(self) -> bool | None:
        """Return True if PSU has a problem."""
        if self.coordinator.data is None or "psu_statuses" not in self.coordinator.data:
            return None
        
        status_value = self.coordinator.data["psu_statuses"].get(self._sensor_key)
        if status_value is None:
            return None
            
        try:
            status_int = int(status_value)
            # Dell iDRAC status values: 1=other, 2=unknown, 3=ok, 4=non_critical, 5=critical, 6=non_recoverable
            # Return True (problem) for anything other than "ok" (3)
            return status_int != 3
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "psu_statuses" not in self.coordinator.data:
            return None
        
        status_value = self.coordinator.data["psu_statuses"].get(self._sensor_key)
        if status_value is None:
            return None
            
        try:
            status_int = int(status_value)
            # Map Dell iDRAC status values to readable strings
            status_map = {
                1: "other",
                2: "unknown", 
                3: "ok",
                4: "non_critical",
                5: "critical",
                6: "non_recoverable"
            }
            status_text = status_map.get(status_int, "unknown")
            
            return {
                "status_code": status_int,
                "status_text": status_text,
            }
        except (ValueError, TypeError):
            return {"raw_value": str(status_value)}