"""Switch platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMMUNITY, CONF_CONNECTION_TYPE, DOMAIN, IDRAC_OIDS
from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)




async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC switches."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    redfish_coordinator = coordinators["redfish"]
    
    entities: list[IdracSwitch] = []
    
    # Only create control switches if Redfish coordinator is available
    # Control operations require Redfish API
    if redfish_coordinator and redfish_coordinator.last_update_success:
        entities.append(IdracIdentifyLEDSwitch(redfish_coordinator, config_entry))
        _LOGGER.info("Successfully created %d switch entities for iDRAC", len(entities))
    else:
        # SNMP-only mode - no control switches
        _LOGGER.debug("Skipping switch creation for SNMP-only mode")

    async_add_entities(entities)


class IdracSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Dell iDRAC switches."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        switch_key: str,
        switch_name: str,
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._switch_key = switch_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Set entity name with device prefix for proper entity ID generation
        # Home Assistant will automatically sanitize for entity IDs
        self._attr_name = f"Dell iDRAC {coordinator.host} {switch_name}"
        # Use stable unique_id based on device_id and switch key
        self._attr_unique_id = f"{device_id}_{switch_key}"
        self._attr_device_class = device_class

        # Store reference details for logging
        self._host = host
        self._port = port

        # Device info will be set in async_added_to_hass

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Set device info now that we can make async calls
        try:
            self._attr_device_info = await self.coordinator.get_device_info()
        except Exception as exc:
            _LOGGER.warning("Failed to get device info for switch: %s", exc)
            # Provide fallback device info to ensure device is created
            self._attr_device_info = {
                "identifiers": {("idrac", self.coordinator.host)},
                "name": f"Dell iDRAC ({self.coordinator.host})",
                "manufacturer": "Dell",
                "model": "iDRAC",
                "configuration_url": f"https://{self.coordinator.host}",
            }

    @property
    def device_info(self):
        """Return device information."""
        # Always return device info - use fallback if not set
        if hasattr(self, '_attr_device_info') and self._attr_device_info:
            return self._attr_device_info
        
        # Fallback device info
        return {
            "identifiers": {("idrac", self.coordinator.host)},
            "name": f"Dell iDRAC ({self.coordinator.host})",
            "manufacturer": "Dell", 
            "model": "iDRAC",
            "configuration_url": f"https://{self.coordinator.host}",
        }

    async def _async_snmp_set(self, oid: str, value: int) -> bool:
        """Send SNMP SET command using coordinator's SNMP connection."""
        if self.coordinator.connection_type not in ["snmp", "hybrid"]:
            _LOGGER.error("SNMP commands only available when using SNMP or hybrid connection")
            return False
            
        # Use coordinator's unified SNMP interface
        result = await self.coordinator.async_set_snmp_value(oid, value)
        
        if result:
            _LOGGER.info("Successfully executed %s command on %s", self._switch_key, self._host)
        
        return result

    async def _async_snmp_get(self, oid: str) -> int | None:
        """Send SNMP GET command using coordinator's SNMP connection."""
        return await self.coordinator.async_get_snmp_value(oid)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class IdracIdentifyLEDSwitch(IdracSwitch):
    """Dell iDRAC identify LED switch."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the identify LED switch."""
        super().__init__(
            coordinator,
            config_entry,
            "identify_led",
            "Identify LED",
            None,
        )

    @property
    def is_on(self) -> bool:
        """Return if the identify LED is on."""
        if self.coordinator.connection_type in ["redfish", "hybrid"]:
            # Always prioritize real LED state from coordinator data
            if self.coordinator.data:
                led_state = self.coordinator.data.get("indicator_led_state")
                if led_state is not None:
                    is_led_on = led_state in ["Blinking", "Lit"]
                    # Update cache to match real state
                    self._last_led_state = is_led_on
                    return is_led_on
            
            # Fallback only when coordinator data is unavailable
            return getattr(self, '_last_led_state', False)
        return False

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:led-on" if self.is_on else "mdi:led-outline"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the identify LED."""
        if self.coordinator.connection_type in ["redfish", "hybrid"]:
            success = await self.coordinator.async_set_indicator_led("Blinking")
            if success:
                # Cache the LED state and refresh coordinator data
                self._last_led_state = True
                # Request coordinator refresh to get real LED state
                await self.coordinator.async_request_refresh()
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to turn on identify LED for %s", self._host)
        else:
            # LED control via SNMP is not typically available in Dell iDRAC SNMP MIB
            _LOGGER.warning("LED control not available via SNMP")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the identify LED."""
        if self.coordinator.connection_type in ["redfish", "hybrid"]:
            success = await self.coordinator.async_set_indicator_led("Off")
            if success:
                # Cache the LED state and refresh coordinator data
                self._last_led_state = False
                # Request coordinator refresh to get real LED state
                await self.coordinator.async_request_refresh()
                self.async_write_ha_state()
            else:
                _LOGGER.error("Failed to turn off identify LED for %s", self._host)
        else:
            # LED control via SNMP is not typically available in Dell iDRAC SNMP MIB
            _LOGGER.warning("LED control not available via SNMP")

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the identify LED."""
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    @property  
    def available(self) -> bool:
        """Return if entity is available."""
        # Available via Redfish or hybrid mode for LED control
        return self.coordinator.connection_type in ["redfish", "hybrid"] and self.coordinator.last_update_success