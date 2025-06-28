"""Button platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
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
    """Set up the Dell iDRAC buttons."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    redfish_coordinator = coordinators["redfish"]
    
    # Only create control buttons if Redfish coordinator is available
    # Control operations require Redfish API
    if redfish_coordinator and redfish_coordinator.last_update_success:
        entities: list[IdracButton] = [
            IdracPowerOnButton(redfish_coordinator, config_entry),
            IdracPowerOffButton(redfish_coordinator, config_entry),
            IdracRebootButton(redfish_coordinator, config_entry),
        ]
        
        # Safe mode button only for SNMP-capable modes (currently disabled as not working reliably)
        # if coordinator.connection_type == "hybrid":
        #     entities.append(IdracSafeModeButton(coordinator, config_entry))

        async_add_entities(entities)
    else:
        # SNMP-only mode - no control buttons
        _LOGGER.debug("Skipping button creation for SNMP-only mode")


class IdracButton(CoordinatorEntity, ButtonEntity):
    """Base class for Dell iDRAC buttons."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        button_key: str,
        button_name: str,
        device_class: ButtonDeviceClass | None = None,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._button_key = button_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Include device prefix in name for proper entity_id generation
        # We'll set the name later in async_added_to_hass since device_info requires async call
        self._button_name = button_name
        # Use stable unique_id based on device_id and button key
        self._attr_unique_id = f"{device_id}_{button_key}"
        self._attr_device_class = device_class

        # Store reference details for logging
        self._host = host
        self._port = port

        # Device info will be set in async_added_to_hass

    async def _async_redfish_action(self, action: str) -> bool:
        """Execute Redfish power action using coordinator."""
        try:
            success = await self.coordinator.async_reset_system(action)
            if success:
                _LOGGER.info("Successfully executed %s command (%s) on %s", self._button_key, action, self._host)
            else:
                _LOGGER.error("Failed to execute %s command (%s) on %s", self._button_key, action, self._host)
            return success
        except Exception as exc:
            _LOGGER.error("Exception during Redfish %s action: %s", action, exc)
            return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Set device info and name now that we can make async calls
        try:
            self._attr_name = self._button_name
            self._attr_device_info = await self.coordinator.get_device_info()
        except Exception as exc:
            _LOGGER.warning("Failed to get device info for button: %s", exc)
            self._attr_name = self._button_name
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

    def _get_current_power_state(self) -> int | None:
        """Get current power state from coordinator data."""
        if self.coordinator.data is None:
            return None
        
        power_state = self.coordinator.data.get("system_info", {}).get("power_state")
        if power_state is not None:
            try:
                return int(power_state)
            except (ValueError, TypeError):
                return None
        return None


class IdracPowerOnButton(IdracButton):
    """Dell iDRAC power on button."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power on button."""
        super().__init__(
            coordinator,
            config_entry,
            "power_on",
            "Power On",
            ButtonDeviceClass.RESTART,
        )

    @property
    def available(self) -> bool:
        """Return if button is available (only when server is off)."""
        if not super().available:
            return False
        
        power_state = self._get_current_power_state()
        if power_state is None:
            return True  # Allow button if we can't determine state
        
        # Only available when server is off (state 2)
        return power_state == 2

    async def async_press(self) -> None:
        """Power on the system."""
        success = await self._async_redfish_action("On")
        
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracPowerOffButton(IdracButton):
    """Dell iDRAC power off button."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power off button."""
        super().__init__(
            coordinator,
            config_entry,
            "power_off",
            "Power Off",
            ButtonDeviceClass.RESTART,
        )

    @property
    def available(self) -> bool:
        """Return if button is available (only when server is on)."""
        if not super().available:
            return False
        
        power_state = self._get_current_power_state()
        if power_state is None:
            return True  # Allow button if we can't determine state
        
        # Only available when server is on (state 1)
        return power_state == 1

    async def async_press(self) -> None:
        """Power off the system."""
        success = await self._async_redfish_action("ForceOff")
        
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracRebootButton(IdracButton):
    """Dell iDRAC reboot button."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(
            coordinator,
            config_entry,
            "reboot",
            "Reboot",
            ButtonDeviceClass.RESTART,
        )

    @property
    def available(self) -> bool:
        """Return if button is available (only when server is on)."""
        if not super().available:
            return False
        
        power_state = self._get_current_power_state()
        if power_state is None:
            return True  # Allow button if we can't determine state
        
        # Only available when server is on (state 1)
        return power_state == 1

    async def async_press(self) -> None:
        """Reboot the system."""
        success = await self._async_redfish_action("GracefulRestart")
        
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracSafeModeButton(IdracButton):
    """Dell iDRAC safe mode button."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the safe mode button."""
        super().__init__(
            coordinator,
            config_entry,
            "safe_mode",
            "Enter Safe Mode",
        )

    async def async_press(self) -> None:
        """Enter safe mode."""
        _LOGGER.warning("Safe mode not available via Redfish API")