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
    UsmUserData,
    getCmd,
)
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.proto import rfc1905, rfc3414

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_USERNAME,
    CONF_AUTH_PROTOCOL,
    CONF_AUTH_PASSWORD,
    CONF_PRIV_PROTOCOL,
    CONF_PRIV_PASSWORD,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_DETAILED_MEMORY,
    CONF_DISCOVERED_POWER_CONSUMPTION,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    DOMAIN,
    IDRAC_OIDS,
    MEMORY_HEALTH_STATUS,
)

_LOGGER = logging.getLogger(__name__)


def _create_auth_data(entry: ConfigEntry) -> CommunityData | UsmUserData:
    """Create the appropriate authentication data for SNMP."""
    snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
    
    if snmp_version == "v3":
        username = entry.data.get(CONF_USERNAME, "")
        auth_protocol = entry.data.get(CONF_AUTH_PROTOCOL, "none")
        auth_password = entry.data.get(CONF_AUTH_PASSWORD, "")
        priv_protocol = entry.data.get(CONF_PRIV_PROTOCOL, "none")
        priv_password = entry.data.get(CONF_PRIV_PASSWORD, "")
        
        # Map protocol names to pysnmp protocol objects
        auth_proto = None
        if auth_protocol != "none":
            if auth_protocol == "md5":
                auth_proto = rfc3414.usmHMACMD5AuthProtocol
            elif auth_protocol == "sha":
                auth_proto = rfc3414.usmHMACSHAAuthProtocol
            elif auth_protocol == "sha224":
                auth_proto = rfc3414.usmHMAC128SHA224AuthProtocol  
            elif auth_protocol == "sha256":
                auth_proto = rfc3414.usmHMAC192SHA256AuthProtocol
            elif auth_protocol == "sha384":
                auth_proto = rfc3414.usmHMAC256SHA384AuthProtocol
            elif auth_protocol == "sha512":
                auth_proto = rfc3414.usmHMAC384SHA512AuthProtocol
        
        priv_proto = None
        if priv_protocol != "none":
            if priv_protocol == "des":
                priv_proto = rfc3414.usmDESPrivProtocol
            elif priv_protocol == "3des":
                priv_proto = rfc3414.usm3DESEDEPrivProtocol
            elif priv_protocol == "aes128":
                priv_proto = rfc3414.usmAesCfb128Protocol
            elif priv_protocol == "aes192":
                priv_proto = rfc3414.usmAesCfb192Protocol
            elif priv_protocol == "aes256":
                priv_proto = rfc3414.usmAesCfb256Protocol
        
        return UsmUserData(
            userName=username,
            authKey=auth_password if auth_proto else None,
            privKey=priv_password if priv_proto else None,
            authProtocol=auth_proto,
            privProtocol=priv_proto,
        )
    else:
        # SNMP v2c
        community = entry.data.get(CONF_COMMUNITY, "public")
        return CommunityData(community)


class IdracDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Dell iDRAC via SNMP."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
        # Keep community for backward compatibility with v2c
        self.community = entry.data.get(CONF_COMMUNITY, "public")
        self.discovered_fans = entry.data.get(CONF_DISCOVERED_FANS, [])
        self.discovered_cpus = entry.data.get(CONF_DISCOVERED_CPUS, [])
        self.discovered_psus = entry.data.get(CONF_DISCOVERED_PSUS, [])
        self.discovered_voltage_probes = entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])
        self.discovered_memory = entry.data.get(CONF_DISCOVERED_MEMORY, [])
        self.discovered_virtual_disks = entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, [])
        self.discovered_physical_disks = entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, [])
        self.discovered_storage_controllers = entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, [])
        self.discovered_detailed_memory = entry.data.get(CONF_DISCOVERED_DETAILED_MEMORY, [])
        self.discovered_power_consumption = entry.data.get(CONF_DISCOVERED_POWER_CONSUMPTION, [])
        self.discovered_system_voltages = entry.data.get(CONF_DISCOVERED_SYSTEM_VOLTAGES, [])

        # Create isolated SNMP engine for this coordinator instance
        self.engine = SnmpEngine()
        self.auth_data = _create_auth_data(entry)
        self.transport_target = UdpTransportTarget((self.host, self.port), timeout=5, retries=1)
        self.context_data = ContextData()
        
        # Store server identification for logging
        self._server_id = f"{self.host}:{self.port}"
        
        # System identification data for device info
        self._device_info = None

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

    async def _async_fetch_device_info(self) -> dict[str, Any]:
        """Fetch device information for device registry."""
        if self._device_info is not None:
            return self._device_info
        
        _LOGGER.debug("Fetching device info for %s", self._server_id)
        
        device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "manufacturer": "Dell",
            "configuration_url": f"https://{self.host}",
        }
        
        # Get system model - try multiple OIDs
        model_name = None
        model_oids = [
            ("primary", IDRAC_OIDS["system_model_name"]),
            ("alternative_1", IDRAC_OIDS["system_model_name_alt"]),
            ("alternative_2", IDRAC_OIDS["system_model_name_alt2"]),
        ]
        
        for oid_name, oid in model_oids:
            model_name = await self._async_get_snmp_string(oid)
            _LOGGER.debug("System model name from %s OID (%s): %s", oid_name, oid, model_name)
            if model_name:
                break
        
        if model_name:
            device_info["model"] = model_name
        else:
            device_info["model"] = "iDRAC"
            _LOGGER.debug("No system model name found from any OID, using default 'iDRAC'")
        
        # Get service tag for serial number
        service_tag = await self._async_get_snmp_string(IDRAC_OIDS["system_service_tag"])
        _LOGGER.debug("Service tag from SNMP: %s", service_tag)
        if service_tag:
            device_info["serial_number"] = service_tag
        
        # Get BIOS version for sw_version
        bios_version = await self._async_get_snmp_string(IDRAC_OIDS["system_bios_version"])
        _LOGGER.debug("BIOS version from SNMP: %s", bios_version)
        if bios_version:
            device_info["sw_version"] = f"BIOS {bios_version}"
        
        # Create name with model if available
        if model_name:
            device_info["name"] = f"Dell {model_name} ({self.host}:{self.port})" if self.port != 161 else f"Dell {model_name} ({self.host})"
        else:
            device_info["name"] = f"Dell iDRAC ({self.host}:{self.port})" if self.port != 161 else f"Dell iDRAC ({self.host})"
        
        # Get CPU information for additional context
        cpu_brand = await self._async_get_snmp_string(IDRAC_OIDS["cpu_brand"])
        cpu_max_speed = await self._async_get_snmp_value(IDRAC_OIDS["cpu_max_speed"])
        _LOGGER.debug("CPU brand from SNMP: %s", cpu_brand)
        _LOGGER.debug("CPU max speed from SNMP: %s", cpu_max_speed)
        
        # Add CPU info to device attributes if available
        if cpu_brand:
            # CPU brand already contains comprehensive info including base speed
            # Use it as-is to avoid confusion with additional speed values
            device_info["hw_version"] = cpu_brand
        
        self._device_info = device_info
        _LOGGER.debug("Device info: %s", device_info)
        return device_info

    @property 
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info or {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Dell iDRAC ({self.host}:{self.port})" if self.port != 161 else f"Dell iDRAC ({self.host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{self.host}",
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Fetch device info on first run
            if self._device_info is None:
                await self._async_fetch_device_info()
            data = {
                "power": await self._async_get_snmp_value(IDRAC_OIDS["power"]),
                "temp_inlet": await self._async_get_snmp_value(IDRAC_OIDS["temp_inlet"], divide_by=10),
                "temp_outlet": await self._async_get_snmp_value(IDRAC_OIDS["temp_outlet"], divide_by=10),
                "cpu_current_speed": await self._async_get_snmp_value(IDRAC_OIDS["cpu_current_speed"]),
                "cpu_temps": {},
                "fans": {},
                "psu_voltages": {},
                "psu_statuses": {},
                "psu_amperages": {},
                "memory_health": {},
                "detailed_memory": {},
                "system_voltages": {},
                "power_consumption": {},
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

            # Get memory health data - FIXED with verified OIDs from discovery
            for memory_index in self.discovered_memory:
                # Use verified working OID with correct indexing pattern
                memory_oid = f"{IDRAC_OIDS['memory_health_base']}.{memory_index}"  # 1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.X
                health_value = await self._async_get_snmp_value(memory_oid)
                
                if health_value is not None:
                    data["memory_health"][f"memory_{memory_index}"] = health_value
                    _LOGGER.debug("Memory health module %d: status=%s (%s)", memory_index, health_value, MEMORY_HEALTH_STATUS.get(health_value, "unknown"))
                else:
                    _LOGGER.debug("Memory health sensor %d returned no value", memory_index)
            
            # Get detailed memory information (new feature from discovery)
            for memory_index in self.discovered_detailed_memory:
                memory_data = {
                    "size_kb": await self._async_get_snmp_value(f"{IDRAC_OIDS['memory_device_size']}.{memory_index}"),
                    "speed_mhz": await self._async_get_snmp_value(f"{IDRAC_OIDS['memory_device_speed']}.{memory_index}"),
                    "type_code": await self._async_get_snmp_value(f"{IDRAC_OIDS['memory_device_type']}.{memory_index}"),
                    "manufacturer": await self._async_get_snmp_string(f"{IDRAC_OIDS['memory_device_manufacturer']}.{memory_index}"),
                    "part_number": await self._async_get_snmp_string(f"{IDRAC_OIDS['memory_device_part_number']}.{memory_index}"),
                    "serial_number": await self._async_get_snmp_string(f"{IDRAC_OIDS['memory_device_serial']}.{memory_index}"),
                    "bank_location": await self._async_get_snmp_string(f"{IDRAC_OIDS['memory_device_bank']}.{memory_index}"),
                    "device_location": await self._async_get_snmp_string(f"{IDRAC_OIDS['memory_device_location']}.{memory_index}"),
                }
                
                # Only include if we got at least the size (indicates module is present)
                if memory_data["size_kb"] is not None and memory_data["size_kb"] > 0:
                    data["detailed_memory"][f"memory_detail_{memory_index}"] = memory_data
                    _LOGGER.debug("Detailed memory module %d: %s MB, %s MHz, %s", 
                                memory_index, memory_data["size_kb"] // 1024 if memory_data["size_kb"] else "Unknown", 
                                memory_data["speed_mhz"], memory_data["manufacturer"])
            
            # Get system voltage monitoring (new feature from discovery)
            for voltage_index in self.discovered_system_voltages:
                voltage_data = {
                    "cpu1_vcore_status": await self._async_get_snmp_value(f"{IDRAC_OIDS['system_voltage_cpu1_vcore']}"),
                    "cpu2_vcore_status": await self._async_get_snmp_value(f"{IDRAC_OIDS['system_voltage_cpu2_vcore']}"),
                    "system_3v3_status": await self._async_get_snmp_value(f"{IDRAC_OIDS['system_voltage_3v3']}"),
                    "cpu1_vcore_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['system_voltage_cpu1_name']}"),
                    "cpu2_vcore_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['system_voltage_cpu2_name']}"),
                    "system_3v3_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['system_voltage_3v3_name']}"),
                }
                
                # Add individual voltage sensors 
                if voltage_data["cpu1_vcore_status"] is not None:
                    data["system_voltages"]["cpu1_vcore"] = voltage_data["cpu1_vcore_status"]
                if voltage_data["cpu2_vcore_status"] is not None:
                    data["system_voltages"]["cpu2_vcore"] = voltage_data["cpu2_vcore_status"]
                if voltage_data["system_3v3_status"] is not None:
                    data["system_voltages"]["system_3v3"] = voltage_data["system_3v3_status"]
                
                _LOGGER.debug("System voltages: CPU1=%s, CPU2=%s, 3.3V=%s", 
                            voltage_data["cpu1_vcore_status"], voltage_data["cpu2_vcore_status"], voltage_data["system_3v3_status"])
            
            # Get enhanced power consumption monitoring (new feature from discovery)
            for power_index in self.discovered_power_consumption:
                power_data = {
                    "system_watts": await self._async_get_snmp_value(f"{IDRAC_OIDS['power_consumption_system']}"),  # Fixed: use actual current consumption (140W) not max capacity (644W)
                    "warning_threshold": await self._async_get_snmp_value(f"{IDRAC_OIDS['power_consumption_warning_threshold']}"),
                    "psu1_current": await self._async_get_snmp_value(f"{IDRAC_OIDS['power_consumption_psu1']}", divide_by=10),  # Fixed: convert tenths of amps to amps
                    "psu2_current": await self._async_get_snmp_value(f"{IDRAC_OIDS['power_consumption_psu2']}", divide_by=10),  # Fixed: convert tenths of amps to amps
                    "system_current": await self._async_get_snmp_value(f"{IDRAC_OIDS['power_consumption_system']}"),
                    "psu1_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['power_psu1_name']}"),
                    "psu2_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['power_psu2_name']}"),
                    "system_name": await self._async_get_snmp_string(f"{IDRAC_OIDS['power_system_name']}"),
                }
                
                # Add power consumption sensors with meaningful names
                if power_data["system_watts"] is not None:
                    data["power_consumption"]["system_power_watts"] = power_data["system_watts"]
                if power_data["warning_threshold"] is not None:
                    data["power_consumption"]["warning_threshold_watts"] = power_data["warning_threshold"]
                if power_data["psu1_current"] is not None:
                    data["power_consumption"]["psu1_current_amps"] = power_data["psu1_current"]
                if power_data["psu2_current"] is not None:
                    data["power_consumption"]["psu2_current_amps"] = power_data["psu2_current"]
                if power_data["system_current"] is not None:
                    data["power_consumption"]["system_current_amps"] = power_data["system_current"]
                
                _LOGGER.debug("Power consumption: System=%sW (threshold %sW), PSU1=%sA, PSU2=%sA, System=%sA", 
                            power_data["system_watts"], power_data["warning_threshold"], 
                            power_data["psu1_current"], power_data["psu2_current"], power_data["system_current"])

            # Get virtual disk data
            for vdisk_index in self.discovered_virtual_disks:
                vdisk_oid = f"{IDRAC_OIDS['virtual_disk_state']}.{vdisk_index}"
                vdisk_state = await self._async_get_snmp_value(vdisk_oid)
                # Create entry even if state is None - it will be discovered so should exist
                data["virtual_disks"][f"vdisk_{vdisk_index}"] = {
                    "state": vdisk_state if vdisk_state is not None else 0,  # Default to 0 if state unavailable
                    "name": await self._async_get_snmp_string(f"{IDRAC_OIDS['virtual_disk_name']}.{vdisk_index}"),
                    "size": await self._async_get_snmp_value(f"{IDRAC_OIDS['virtual_disk_size']}.{vdisk_index}"),
                    "layout": await self._async_get_snmp_value(f"{IDRAC_OIDS['virtual_disk_layout']}.{vdisk_index}"),
                }

            # Get enhanced physical disk data (with verified OIDs from discovery)
            for pdisk_index in self.discovered_physical_disks:
                pdisk_oid = f"{IDRAC_OIDS['physical_disk_state']}.{pdisk_index}"
                pdisk_state = await self._async_get_snmp_value(pdisk_oid)
                
                # Get enhanced disk information
                disk_data = {
                    "state": pdisk_state if pdisk_state is not None else 0,
                    "capacity": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_capacity']}.{pdisk_index}"),
                    "used_space": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_used_space']}.{pdisk_index}"),
                    "serial": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_serial']}.{pdisk_index}"),
                    # Enhanced attributes from discovery
                    "name": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_name']}.{pdisk_index}"),
                    "vendor": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_vendor']}.{pdisk_index}"),
                    "product_id": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_product_id']}.{pdisk_index}"),
                    "revision": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_revision']}.{pdisk_index}"),
                    "size_mb": await self._async_get_snmp_value(f"{IDRAC_OIDS['physical_disk_size_mb']}.{pdisk_index}"),
                    "fqdd": await self._async_get_snmp_string(f"{IDRAC_OIDS['physical_disk_fqdd']}.{pdisk_index}"),
                }
                
                data["physical_disks"][f"pdisk_{pdisk_index}"] = disk_data
                
                _LOGGER.debug("Physical disk %d: %s %s %s (%s MB)", pdisk_index, 
                            disk_data["vendor"], disk_data["product_id"], disk_data["name"], disk_data["size_mb"])

            # Get storage controller data
            for controller_index in self.discovered_storage_controllers:
                controller_oid = f"{IDRAC_OIDS['controller_state']}.{controller_index}"
                controller_state = await self._async_get_snmp_value(controller_oid)
                battery_state = await self._async_get_snmp_value(f"{IDRAC_OIDS['controller_battery_state']}.{controller_index}")
                
                # Get additional diagnostic information (updated with verified OIDs)
                rollup_status = await self._async_get_snmp_value(f"{IDRAC_OIDS['controller_rollup_status']}.{controller_index}")
                controller_name = await self._async_get_snmp_string(f"{IDRAC_OIDS['controller_name']}.{controller_index}")
                firmware_version = await self._async_get_snmp_string(f"{IDRAC_OIDS['controller_firmware']}.{controller_index}")
                cache_size = await self._async_get_snmp_value(f"{IDRAC_OIDS['controller_cache_size']}.{controller_index}")  # Fixed OID from discovery
                rebuild_rate = await self._async_get_snmp_value(f"{IDRAC_OIDS['controller_rebuild_rate']}.{controller_index}")  # Fixed OID from discovery
                
                # Debug logging to show actual numeric values and diagnostic info
                _LOGGER.debug(
                    f"Storage Controller {controller_index} - Raw state value: {controller_state} "
                    f"(type: {type(controller_state)}), Battery state: {battery_state}, "
                    f"Rollup status: {rollup_status}, Name: {controller_name}, "
                    f"Firmware: {firmware_version}, Cache size: {cache_size}, Rebuild rate: {rebuild_rate}"
                )
                
                # Create entry even if state is None - it will be discovered so should exist
                data["storage_controllers"][f"controller_{controller_index}"] = {
                    "state": controller_state if controller_state is not None else 0,  # Default to 0 if state unavailable
                    "battery_state": battery_state,
                    "rollup_status": rollup_status,
                    "name": controller_name,
                    "firmware_version": firmware_version,
                    "cache_size": cache_size,
                    "rebuild_rate": rebuild_rate,
                }

            return data

        except Exception as exc:
            raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc

    async def _async_get_snmp_value(self, oid: str, divide_by: int = 1) -> float | None:
        """Get a single SNMP value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
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

    async def _async_get_snmp_string(self, oid: str) -> str | None:
        """Get a single SNMP string value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication or error_status:
                _LOGGER.debug("SNMP error for OID %s: %s", oid, error_indication or error_status)
                return None

            if var_binds:
                value_str = str(var_binds[0][1]).strip()
                if value_str and "No Such Object" not in value_str and "No Such Instance" not in value_str:
                    return value_str
                else:
                    _LOGGER.debug("Invalid SNMP string value for OID %s: %s", oid, value_str)
                    return None

            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP string for OID %s: %s", oid, exc)
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