"""Switch platform for Dell iDRAC integration."""
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
    getCmd,
)

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Dell iDRAC switches."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracSwitch] = [
        IdracPowerControlSwitch(coordinator, config_entry),
        IdracIdentifyLEDSwitch(coordinator, config_entry),
        IdracSafeModeSwitch(coordinator, config_entry),
    ]

    async_add_entities(entities)


class IdracSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Dell iDRAC switches."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        switch_key: str,
        switch_name: str,
        control_oid: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._switch_key = switch_key
        self._control_oid = control_oid
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Include device prefix in name for proper entity_id generation
        device_prefix = _get_device_name_prefix(host)
        self._attr_name = f"{device_prefix} {switch_name}"
        # Use stable unique_id based on device_id and switch key
        self._attr_unique_id = f"{device_id}_{switch_key}"

        # Store SNMP connection details
        self._host = host
        self._port = port
        self._community = config_entry.data[CONF_COMMUNITY]

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{host}",
        }

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

            _LOGGER.debug("Successfully set OID %s to value %s", oid, value)
            return True

        except Exception as exc:
            _LOGGER.error("Exception during SNMP SET for OID %s: %s", oid, exc)
            return False

    async def _async_snmp_get(self, oid: str) -> int | None:
        """Send SNMP GET command."""
        try:
            engine = SnmpEngine()
            community_data = CommunityData(self._community)
            transport_target = UdpTransportTarget((self._host, self._port), timeout=5, retries=1)
            context_data = ContextData()

            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication or error_status:
                _LOGGER.debug("SNMP GET error for OID %s: %s", oid, error_indication or error_status)
                return None

            if var_binds:
                try:
                    return int(var_binds[0][1])
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not convert SNMP value to int for OID %s: %s", oid, var_binds[0][1])
                    return None

            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP value for OID %s: %s", oid, exc)
            return None


class IdracPowerControlSwitch(IdracSwitch):
    """Dell iDRAC system power control switch."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power control switch."""
        super().__init__(
            coordinator,
            config_entry,
            "power_control",
            "System Power",
            IDRAC_OIDS["power_control"],
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the system is powered on."""
        if self.coordinator.data is None:
            return None
        
        # Get power state from coordinator data
        power_state = self.coordinator.data.get("system_power_state")
        if power_state is not None:
            # Dell iDRAC power states: 1=on, 2=off
            return power_state == 1
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the system."""
        success = await self._async_snmp_set(self._control_oid, 1)
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the system."""
        success = await self._async_snmp_set(self._control_oid, 2)
        if success:
            # Request coordinator update to reflect the change
            await self.coordinator.async_request_refresh()


class IdracIdentifyLEDSwitch(IdracSwitch):
    """Dell iDRAC identify LED control switch."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the identify LED switch."""
        super().__init__(
            coordinator,
            config_entry,
            "identify_led",
            "Identify LED",
            IDRAC_OIDS["identify_led"],
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the identify LED is on."""
        # Check current LED state via SNMP
        # This is updated less frequently, so we'll check directly
        return None  # Will be implemented with real-time checking

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the identify LED."""
        await self._async_snmp_set(self._control_oid, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the identify LED."""
        await self._async_snmp_set(self._control_oid, 0)


class IdracSafeModeSwitch(IdracSwitch):
    """Dell iDRAC safe mode toggle switch."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the safe mode switch."""
        super().__init__(
            coordinator,
            config_entry,
            "safe_mode",
            "Safe Mode",
            IDRAC_OIDS["safe_mode"],
        )

    @property
    def is_on(self) -> bool | None:
        """Return if safe mode is enabled."""
        # Check current safe mode state via SNMP
        return None  # Will be implemented with real-time checking

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable safe mode."""
        await self._async_snmp_set(self._control_oid, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable safe mode."""
        await self._async_snmp_set(self._control_oid, 0)