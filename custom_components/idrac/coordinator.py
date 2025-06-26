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
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
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
        self.discovered_memory = entry.data.get(CONF_DISCOVERED_MEMORY, [])
        self.discovered_virtual_disks = entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, [])
        self.discovered_physical_disks = entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, [])
        self.discovered_storage_controllers = entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, [])

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
                "memory_health": {},
                "virtual_disks": {},
                "physical_disks": {},
                "storage_controllers": {},
                # System status with fallback OIDs
                "system_health": await self._async_get_snmp_value(IDRAC_OIDS["system_health"]),
                "system_power_state": await self._async_get_snmp_value_with_multiple_fallbacks([
                    IDRAC_OIDS["system_power_state"],
                    IDRAC_OIDS["system_power_state_alt"],
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.6.1.1",  # Additional fallback
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1"     # Simplified OID
                ]),
                "system_intrusion": await self._async_get_snmp_value_with_multiple_fallbacks([
                    # Dell chassis intrusion detection OIDs
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.25.1.1", # Chassis security breach detection status
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.24.1.1", # Chassis security breach sensor status
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.27.1.1", # System chassis intrusion status
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.26.1.1", # System chassis intrusion reading
                    # Simplified versions without table indices
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.25.1",   
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.24.1",   
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.27.1",   
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.26.1",   
                    # Even simpler base OIDs
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.25",     
                    "1.3.6.1.4.1.674.10892.5.4.300.70.1.24",     
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.27",     
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.26",
                    # Dell older iDRAC versions
                    "1.3.6.1.4.1.674.10892.1.300.70.1.25.1.1",  # Legacy chassis intrusion
                    "1.3.6.1.4.1.674.10892.1.300.70.1.24.1.1",  # Legacy chassis security
                    # Generic system status that might include intrusion
                    "1.3.6.1.4.1.674.10892.5.2.2.0",            # System status
                    "1.3.6.1.4.1.674.10892.5.2.3.0"             # System health rollup
                ]),
                "psu_redundancy": await self._async_get_snmp_value_with_multiple_fallbacks([
                    IDRAC_OIDS["psu_redundancy"],
                    IDRAC_OIDS["psu_redundancy_alt"],
                    "1.3.6.1.4.1.674.10892.5.4.200.10.1.42.1.1", # Additional fallback
                    "1.3.6.1.4.1.674.10892.1.600.12.1.5.1.1"     # Legacy OID
                ]),
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
                if voltage_value is not None and 3 <= voltage_value <= 240:  # Valid PSU voltage range 3V-240V
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

            # Get memory health data - try multiple OID bases if discovery found modules
            for memory_index in self.discovered_memory:
                # Try multiple memory health OID bases to find working ones
                memory_oid_bases = [
                    IDRAC_OIDS['memory_health_base'],                 # Primary: 1.3.6.1.4.1.674.10892.5.4.1100.50.1.5
                    "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6",         # Alternative memory health status
                    "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20",        # Memory device status
                    "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7",         # Memory operational status
                ]
                
                health_value = None
                for oid_base in memory_oid_bases:
                    memory_oid = f"{oid_base}.{memory_index}"
                    health_value = await self._async_get_snmp_value(memory_oid)
                    if health_value is not None:
                        _LOGGER.debug("Found memory health for module %d using OID %s: %s", memory_index, memory_oid, health_value)
                        break
                
                if health_value is not None:  # Health status can be various values
                    data["memory_health"][f"memory_{memory_index}"] = health_value
                else:
                    _LOGGER.debug("Memory health sensor %d returned invalid value from all OIDs", memory_index)

            # Get virtual disk data
            for vdisk_index in self.discovered_virtual_disks:
                vdisk_oid = f"{IDRAC_OIDS['virtual_disk_state']}.{vdisk_index}"
                vdisk_state = await self._async_get_snmp_value(vdisk_oid)
                if vdisk_state is not None:
                    data["virtual_disks"][f"vdisk_{vdisk_index}"] = {
                        "state": vdisk_state,
                        "name": await self._async_get_snmp_value(f"{IDRAC_OIDS['virtual_disk_name']}.{vdisk_index}"),
                        "size": await self._async_get_snmp_value(f"{IDRAC_OIDS['virtual_disk_size']}.{vdisk_index}"),
                        "layout": await self._async_get_snmp_value(f"{IDRAC_OIDS['virtual_disk_layout']}.{vdisk_index}"),
                    }

            # Get physical disk data
            for pdisk_index in self.discovered_physical_disks:
                pdisk_oid = f"{IDRAC_OIDS['physical_disk_state']}.{pdisk_index}"
                pdisk_state = await self._async_get_snmp_value(pdisk_oid)
                if pdisk_state is not None:
                    data["physical_disks"][f"pdisk_{pdisk_index}"] = {
                        "state": pdisk_state,
                        "capacity": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_capacity']}.{pdisk_index}"),
                        "used_space": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_used_space']}.{pdisk_index}"),
                        "serial": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_serial']}.{pdisk_index}"),
                    }

            # Get storage controller data
            for controller_index in self.discovered_storage_controllers:
                controller_oid = f"{IDRAC_OIDS['controller_state']}.{controller_index}"
                controller_state = await self._async_get_snmp_value(controller_oid)
                if controller_state is not None:
                    data["storage_controllers"][f"controller_{controller_index}"] = {
                        "state": controller_state,
                        "battery_state": await self._async_get_snmp_value(f"{IDRAC_OIDS['controller_battery_state']}.{controller_index}"),
                    }

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

    async def _async_get_snmp_value_with_fallback(self, primary_oid: str, fallback_oid: str, divide_by: int = 1) -> float | None:
        """Get SNMP value with fallback to alternative OID."""
        # Try primary OID first
        value = await self._async_get_snmp_value(primary_oid, divide_by)
        if value is not None:
            _LOGGER.debug("Successfully got value from primary OID %s: %s", primary_oid, value)
            return value
        
        # Fall back to alternative OID
        _LOGGER.debug("Primary OID %s failed, trying fallback OID %s", primary_oid, fallback_oid)
        value = await self._async_get_snmp_value(fallback_oid, divide_by)
        if value is not None:
            _LOGGER.debug("Successfully got value from fallback OID %s: %s", fallback_oid, value)
        
        return value

    async def _async_get_snmp_value_with_multiple_fallbacks(self, oids: list[str], divide_by: int = 1) -> float | None:
        """Get SNMP value with multiple fallback OIDs."""
        for i, oid in enumerate(oids):
            value = await self._async_get_snmp_value(oid, divide_by)
            if value is not None:
                if i == 0:
                    _LOGGER.debug("Successfully got value from primary OID %s: %s", oid, value)
                else:
                    _LOGGER.debug("Successfully got value from fallback OID %s (attempt %d): %s", oid, i + 1, value)
                return value
            else:
                _LOGGER.debug("OID %s failed (attempt %d)", oid, i + 1)
        
        _LOGGER.debug("All OIDs failed for fallback chain: %s", oids)
        return None