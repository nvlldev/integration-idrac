"""DataUpdateCoordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMUNITY,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IDRAC_OIDS,
)

_LOGGER = logging.getLogger(__name__)


class IdracDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Dell iDRAC via SNMP."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.community = entry.data[CONF_COMMUNITY]
        self.discovered_fans = entry.data.get(CONF_DISCOVERED_FANS, [])
        self.discovered_cpus = entry.data.get(CONF_DISCOVERED_CPUS, [])

        # Create isolated SNMP engine for this coordinator instance
        self.engine = SnmpEngine()
        self.community_data = CommunityData(self.community)
        self.transport_target = UdpTransportTarget((self.host, self.port), timeout=5, retries=1)
        self.context_data = ContextData()
        
        # Store server identification for logging
        self._server_id = f"{self.host}:{self.port}"

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            data = {
                "power": await self._async_get_snmp_value(IDRAC_OIDS["power"]),
                "temp_inlet": await self._async_get_snmp_value(IDRAC_OIDS["temp_inlet"], divide_by=10),
                "temp_outlet": await self._async_get_snmp_value(IDRAC_OIDS["temp_outlet"], divide_by=10),
                "cpu_temps": {},
                "fans": {},
            }

            # Get CPU temperature data
            for cpu_index in self.discovered_cpus:
                cpu_oid = f"{IDRAC_OIDS['temp_cpu_base']}.{cpu_index}"
                cpu_value = await self._async_get_snmp_value(cpu_oid, divide_by=10)
                if cpu_value is not None:
                    data["cpu_temps"][f"cpu_{cpu_index}"] = cpu_value

            # Get fan speed data
            for fan_index in self.discovered_fans:
                fan_oid = f"{IDRAC_OIDS['fan_base']}.{fan_index}"
                fan_value = await self._async_get_snmp_value(fan_oid)
                if fan_value is not None:
                    data["fans"][f"fan_{fan_index}"] = fan_value

            return data

        except Exception as exc:
            raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc

    async def _async_get_snmp_value(self, oid: str, divide_by: int = 1) -> float | None:
        """Get a single SNMP value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.community_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication or error_status:
                _LOGGER.debug("SNMP error for OID %s: %s", oid, error_indication or error_status)
                return None

            if var_binds:
                try:
                    value = float(var_binds[0][1])
                    return value / divide_by
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not convert SNMP value to float for OID %s: %s", oid, var_binds[0][1])
                    return None

            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP value for OID %s: %s", oid, exc)
            return None