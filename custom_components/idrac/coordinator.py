"""DataUpdateCoordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from easysnmp import Session
from easysnmp.exceptions import EasySNMPConnectionError, EasySNMPTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_COMMUNITY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, IDRAC_OIDS, CONF_DISCOVERED_FANS, CONF_DISCOVERED_CPUS

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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            data = {}

            data["power"] = await self._async_get_snmp_value(IDRAC_OIDS["power"])

            data["temp_inlet"] = await self._async_get_snmp_value(IDRAC_OIDS["temp_inlet"], divide_by=10)
            data["temp_outlet"] = await self._async_get_snmp_value(IDRAC_OIDS["temp_outlet"], divide_by=10)

            data["cpu_temps"] = {}
            for cpu_index in self.discovered_cpus:
                cpu_oid = f"{IDRAC_OIDS['temp_cpu_base']}.{cpu_index}"
                try:
                    cpu_value = await self._async_get_snmp_value(cpu_oid, divide_by=10)
                    if cpu_value is not None:
                        data["cpu_temps"][f"cpu_{cpu_index}"] = cpu_value
                except Exception as exc:
                    _LOGGER.debug("Could not get CPU %d temperature data: %s", cpu_index, exc)

            data["fans"] = {}
            for fan_index in self.discovered_fans:
                fan_oid = f"{IDRAC_OIDS['fan_base']}.{fan_index}"
                try:
                    fan_value = await self._async_get_snmp_value(fan_oid)
                    if fan_value is not None:
                        data["fans"][f"fan_{fan_index}"] = fan_value
                except Exception as exc:
                    _LOGGER.debug("Could not get fan %d data: %s", fan_index, exc)

            return data

        except Exception as exc:
            raise UpdateFailed(f"Error communicating with iDRAC: {exc}") from exc

    async def _async_get_snmp_value(self, oid: str, divide_by: int = 1) -> float | None:
        """Get a single SNMP value."""
        try:
            def get_snmp_value():
                session = Session(hostname=self.host, community=self.community, version=2, timeout=5, retries=1)
                result = session.get(oid)
                return result.value

            value_str = await self.hass.async_add_executor_job(get_snmp_value)
            
            if value_str is not None:
                try:
                    value = float(value_str)
                    return value / divide_by
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert SNMP value to float for OID %s: %s", oid, value_str)
                    return None

            return None

        except (EasySNMPConnectionError, EasySNMPTimeoutError) as exc:
            _LOGGER.warning("SNMP connection error for OID %s: %s", oid, exc)
            return None
        except Exception as exc:
            _LOGGER.warning("Exception getting SNMP value for OID %s: %s", oid, exc)
            return None