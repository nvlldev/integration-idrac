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
from pysnmp.proto.rfc1902 import Integer as SnmpInteger

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COMMUNITY, DOMAIN, IDRAC_OIDS
from .coordinator import IdracDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_device_name_prefix(coordinator: IdracDataUpdateCoordinator) -> str:
    """Get device name prefix for entity naming."""
    device_info = coordinator.device_info
    if device_info and "model" in device_info and device_info["model"] != "iDRAC":
        return f"Dell {device_info['model']} ({coordinator.host})"
    else:
        return f"Dell iDRAC ({coordinator.host})"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC switches."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracSwitch] = [
        IdracIdentifyLEDSwitch(coordinator, config_entry),
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
        device_class: SwitchDeviceClass | None = None,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._switch_key = switch_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Include device prefix in name for proper entity_id generation
        device_prefix = _get_device_name_prefix(coordinator)
        self._attr_name = f"{device_prefix} {switch_name}"
        # Use stable unique_id based on device_id and switch key
        self._attr_unique_id = f"{device_id}_{switch_key}"
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
                ObjectType(ObjectIdentity(oid), SnmpInteger(value)),
            )

            if error_indication:
                _LOGGER.error("SNMP SET error indication for OID %s: %s", oid, error_indication)
                return False
            
            if error_status:
                _LOGGER.error("SNMP SET error status for OID %s: %s", oid, error_status)
                return False

            _LOGGER.info("Successfully executed %s command on %s", self._switch_key, self._host)
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class IdracIdentifyLEDSwitch(IdracSwitch):
    """Dell iDRAC identify LED switch."""

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
            None,
        )
        # Initialize LED state as False
        self._led_state = False

    @property
    def is_on(self) -> bool:
        """Return if the identify LED is on."""
        return self._led_state

    @property
    def icon(self) -> str:
        """Return the icon for the switch."""
        return "mdi:led-on" if self.is_on else "mdi:led-outline"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the identify LED."""
        success = await self._async_snmp_set(IDRAC_OIDS["identify_led"], 1)
        if success:
            self._led_state = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn on identify LED for %s", self._host)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the identify LED."""
        success = await self._async_snmp_set(IDRAC_OIDS["identify_led"], 0)
        if success:
            self._led_state = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to turn off identify LED for %s", self._host)

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the identify LED."""
        if self.is_on:
            await self.async_turn_off(**kwargs)
        else:
            await self.async_turn_on(**kwargs)

    @property  
    def available(self) -> bool:
        """Return if entity is available."""
        return True  # Always available since it's a control switch