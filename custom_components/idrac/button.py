"""Button platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CONF_COMMUNITY, CONF_CONNECTION_TYPE, DOMAIN, IDRAC_OIDS
from .coordinator_redfish import RedfishDataUpdateCoordinator
from .entity_base import IdracEntityBase

_LOGGER = logging.getLogger(__name__)




async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC buttons."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    redfish_coordinator = coordinators["redfish"]
    
    entities: list[IdracButton] = []
    
    # Only create control buttons if Redfish coordinator is available
    # Control operations require Redfish API
    if redfish_coordinator and redfish_coordinator.last_update_success:
        entities.extend([
            IdracPowerOnButton(redfish_coordinator, config_entry),
            IdracShutdownButton(redfish_coordinator, config_entry),
            IdracPowerOffButton(redfish_coordinator, config_entry),
            IdracRebootButton(redfish_coordinator, config_entry),
        ])
        
        # Safe mode button only for SNMP-capable modes (currently disabled as not working reliably)
        # if coordinator.connection_type == "hybrid":
        #     entities.append(IdracSafeModeButton(coordinator, config_entry))

        _LOGGER.info("Successfully created %d button entities for iDRAC", len(entities))
    else:
        # SNMP-only mode - no control buttons
        _LOGGER.debug("Skipping button creation for SNMP-only mode")

    async_add_entities(entities)


class IdracButton(IdracEntityBase, ButtonEntity):
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
        super().__init__(coordinator, config_entry, button_key, button_name)
        self._attr_device_class = device_class

    async def _async_redfish_action(self, action: str) -> bool:
        """Execute Redfish power action using coordinator."""
        try:
            success = await self.coordinator.async_reset_system(action)
            if success:
                _LOGGER.info("Successfully executed %s command (%s) on %s", self._entity_key, action, self._host)
            else:
                _LOGGER.error("Failed to execute %s command (%s) on %s", self._entity_key, action, self._host)
            return success
        except Exception as exc:
            _LOGGER.error("Exception during Redfish %s action: %s", action, exc)
            return False

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


class IdracShutdownButton(IdracButton):
    """Dell iDRAC graceful shutdown button."""

    def __init__(
        self,
        coordinator: RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the shutdown button."""
        super().__init__(
            coordinator,
            config_entry,
            "shutdown",
            "Shutdown",
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
        """Gracefully shutdown the system."""
        success = await self._async_redfish_action("GracefulShutdown")
        
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracPowerOffButton(IdracButton):
    """Dell iDRAC hard power off button."""

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
        """Force power off the system (hard power cut)."""
        _LOGGER.warning("Hard power off requested - this will immediately cut power!")
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
        # Try graceful restart first, fallback to force restart if needed
        success = await self._async_redfish_action("GracefulRestart")
        
        if not success:
            _LOGGER.warning("GracefulRestart failed, trying ForceRestart for %s", self._host)
            success = await self._async_redfish_action("ForceRestart")
        
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Both GracefulRestart and ForceRestart failed for %s", self._host)


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