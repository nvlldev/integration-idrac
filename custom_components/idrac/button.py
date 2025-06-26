"""Button platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    setCmd,
)

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMMUNITY, DOMAIN, IDRAC_OIDS
from .coordinator import IdracDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_device_name_prefix(host: str) -> str:
    """Get device name prefix for entity naming."""
    return f"Dell iDRAC ({host})"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC buttons."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracButton] = [
        IdracPowerOnButton(coordinator, config_entry),
        IdracPowerOffButton(coordinator, config_entry),
        IdracRebootButton(coordinator, config_entry),
        IdracSafeModeButton(coordinator, config_entry),
    ]

    async_add_entities(entities)


class IdracButton(CoordinatorEntity, ButtonEntity):
    """Base class for Dell iDRAC buttons."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
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
        device_prefix = _get_device_name_prefix(host)
        self._attr_name = f"{device_prefix} {button_name}"
        # Use stable unique_id based on device_id and button key
        self._attr_unique_id = f"{device_id}_{button_key}"
        self._attr_device_class = device_class

        # Store SNMP connection details
        self._host = host
        self._port = port
        self._community = config_entry.data[CONF_COMMUNITY]

        self._attr_device_info = coordinator.device_info

    async def _async_snmp_set(self, oid: str, value: int) -> bool:
        """Send SNMP SET command."""
        try:
            engine = SnmpEngine()
            community_data = CommunityData(self._community)
            transport_target = UdpTransportTarget((self._host, self._port), timeout=10, retries=2)
            context_data = ContextData()

            error_indication, error_status, error_index, var_binds = await setCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(oid), value),
            )

            if error_indication:
                _LOGGER.error("SNMP SET error indication for OID %s: %s", oid, error_indication)
                return False
            
            if error_status:
                _LOGGER.error("SNMP SET error status for OID %s: %s", oid, error_status)
                return False

            _LOGGER.info("Successfully executed %s command on %s", self._button_key, self._host)
            return True

        except Exception as exc:
            _LOGGER.error("Exception during SNMP SET for OID %s: %s", oid, exc)
            return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    def _get_current_power_state(self) -> int | None:
        """Get current power state from coordinator data."""
        if self.coordinator.data is None:
            return None
        
        power_state = self.coordinator.data.get("system_power_state")
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
        coordinator: IdracDataUpdateCoordinator,
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
        # Double-check power state before executing
        power_state = self._get_current_power_state()
        if power_state == 1:  # Already on
            _LOGGER.warning("Cannot power on %s - server is already powered on", self._host)
            return
        
        success = await self._async_snmp_set(IDRAC_OIDS["power_control"], 1)
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracPowerOffButton(IdracButton):
    """Dell iDRAC power off button."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
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
        # Double-check power state before executing
        power_state = self._get_current_power_state()
        if power_state == 2:  # Already off
            _LOGGER.warning("Cannot power off %s - server is already powered off", self._host)
            return
        
        success = await self._async_snmp_set(IDRAC_OIDS["power_control"], 2)
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracRebootButton(IdracButton):
    """Dell iDRAC reboot button."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
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
        # Double-check power state before executing
        power_state = self._get_current_power_state()
        if power_state == 2:  # Server is off
            _LOGGER.warning("Cannot reboot %s - server is powered off", self._host)
            return
        
        success = await self._async_snmp_set(IDRAC_OIDS["power_control"], 3)
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracSafeModeButton(IdracButton):
    """Dell iDRAC safe mode button."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
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
        await self._async_snmp_set(IDRAC_OIDS["safe_mode"], 1)