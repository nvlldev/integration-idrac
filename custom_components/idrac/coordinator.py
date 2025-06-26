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
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_SCAN_INTERVAL,
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
        self.discovered_psus = entry.data.get(CONF_DISCOVERED_PSUS, [])
        self.discovered_voltage_probes = entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])

        # Create isolated SNMP engine for this coordinator instance
        self.engine = SnmpEngine()
        self.community_data = CommunityData(self.community)
        self.transport_target = UdpTransportTarget((self.host, self.port), timeout=5, retries=1)
        self.context_data = ContextData()
        
        # Store server identification for logging
        self._server_id = f"{self.host}:{self.port}"

        # Get scan interval from options first, then config data, then default
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
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
                "psu_voltages": {},
                "psu_statuses": {},
                "psu_amperages": {},
            }

            # Get CPU temperature data - only include sensors with valid data
            for cpu_index in self.discovered_cpus:
                cpu_oid = f"{IDRAC_OIDS['temp_cpu_base']}.{cpu_index}"
                cpu_value = await self._async_get_snmp_value(cpu_oid, divide_by=10)
                if cpu_value is not None and cpu_value > 0:  # Valid temperature should be > 0
                    data["cpu_temps"][f"cpu_{cpu_index}"] = cpu_value
                else:
                    _LOGGER.debug("CPU sensor %d returned invalid value: %s", cpu_index, cpu_value)

            # Get fan speed data - only include sensors with valid data
            for fan_index in self.discovered_fans:
                fan_oid = f"{IDRAC_OIDS['fan_base']}.{fan_index}"
                fan_value = await self._async_get_snmp_value(fan_oid)
                if fan_value is not None and fan_value > 0:  # Valid fan speed should be > 0
                    data["fans"][f"fan_{fan_index}"] = fan_value
                else:
                    _LOGGER.debug("Fan sensor %d returned invalid value: %s", fan_index, fan_value)

            # Get PSU voltage data - only include sensors with valid data
            for voltage_probe_index in self.discovered_voltage_probes:
                voltage_oid = f"{IDRAC_OIDS['psu_voltage_base']}.{voltage_probe_index}"
                voltage_value = await self._async_get_snmp_value(voltage_oid, divide_by=1000)  # Convert mV to V
                if voltage_value is not None and voltage_value > 0:  # Valid voltage should be > 0
                    data["psu_voltages"][f"psu_voltage_{voltage_probe_index}"] = voltage_value
                else:
                    _LOGGER.debug("Voltage probe sensor %d returned invalid value: %s", voltage_probe_index, voltage_value)

            # Get PSU status data - only include sensors with valid data
            for psu_index in self.discovered_psus:
                status_oid = f"{IDRAC_OIDS['psu_status_base']}.{psu_index}"
                status_value = await self._async_get_snmp_value(status_oid)
                if status_value is not None:  # Status can be 0 (but typically starts from 1)
                    data["psu_statuses"][f"psu_status_{psu_index}"] = status_value
                else:
                    _LOGGER.debug("PSU status sensor %d returned invalid value: %s", psu_index, status_value)

            # Get PSU amperage data - only include sensors with valid data
            for psu_index in self.discovered_psus:
                amperage_oid = f"{IDRAC_OIDS['psu_amperage_base']}.{psu_index}"
                amperage_value = await self._async_get_snmp_value(amperage_oid, divide_by=10)  # Convert tenths of amps to amps
                if amperage_value is not None and amperage_value >= 0:  # Valid amperage should be >= 0
                    data["psu_amperages"][f"psu_amperage_{psu_index}"] = amperage_value
                else:
                    _LOGGER.debug("PSU amperage sensor %d returned invalid value: %s", psu_index, amperage_value)

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