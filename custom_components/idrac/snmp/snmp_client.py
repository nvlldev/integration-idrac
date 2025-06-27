"""Dell iDRAC SNMP client."""
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
    UsmUserData,
    getCmd,
)
from pysnmp.proto import rfc1902

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME

from ..const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_AUTH_PROTOCOL,
    CONF_AUTH_PASSWORD,
    CONF_PRIV_PROTOCOL,
    CONF_PRIV_PASSWORD,
    CONF_PORT,
    CONF_SNMP_PORT,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_DETAILED_MEMORY,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    CONF_DISCOVERED_POWER_CONSUMPTION,
    CONF_DISCOVERED_INTRUSION,
    CONF_DISCOVERED_BATTERY,
    CONF_DISCOVERED_PROCESSORS,
    DEFAULT_SNMP_VERSION,
    DEFAULT_SNMP_PORT,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    IDRAC_OIDS,
    PSU_STATUS,
    FAN_STATUS,
    TEMP_STATUS,
    MEMORY_HEALTH_STATUS,
    INTRUSION_STATUS,
    BATTERY_STATUS,
    PROCESSOR_STATUS,
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
            auth_proto = getattr(rfc1902, SNMP_AUTH_PROTOCOLS[auth_protocol], None)
        
        priv_proto = None
        if priv_protocol != "none":
            priv_proto = getattr(rfc1902, SNMP_PRIV_PROTOCOLS[priv_protocol], None)
        
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


class SNMPClient:
    """Dell iDRAC SNMP client for sensor data collection.
    
    This client handles all SNMP operations for Dell iDRAC devices using pysnmp.
    It supports both SNMPv2c and SNMPv3 authentication, manages discovered sensor
    indices, and provides methods for collecting comprehensive sensor data.
    
    The client collects data for:
    - CPU temperature sensors
    - Cooling device (fan) sensors  
    - Power supply status and metrics
    - Voltage probe readings
    - Memory module status
    - Power consumption metrics
    
    Attributes:
        host: iDRAC host address.
        snmp_port: SNMP port (default 161).
        engine: pysnmp SnmpEngine instance.
        auth_data: SNMP authentication data (community or USM).
        discovered_*: Lists of discovered sensor indices.
    """

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the SNMP client.
        
        Args:
            entry: Configuration entry containing SNMP connection details
                  and discovered sensor indices.
        """
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get(CONF_PORT)
        
        # SNMP configuration
        self.snmp_port = entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)
        self.snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
        self.community = entry.data.get(CONF_COMMUNITY, "public")
        
        # Store discovered sensors
        self.discovered_fans = entry.data.get(CONF_DISCOVERED_FANS, [])
        self.discovered_cpus = entry.data.get(CONF_DISCOVERED_CPUS, [])
        self.discovered_psus = entry.data.get(CONF_DISCOVERED_PSUS, [])
        self.discovered_voltage_probes = entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])
        self.discovered_memory = entry.data.get(CONF_DISCOVERED_MEMORY, [])
        self.discovered_virtual_disks = entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, [])
        self.discovered_physical_disks = entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, [])
        self.discovered_storage_controllers = entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, [])
        self.discovered_detailed_memory = entry.data.get(CONF_DISCOVERED_DETAILED_MEMORY, [])
        self.discovered_system_voltages = entry.data.get(CONF_DISCOVERED_SYSTEM_VOLTAGES, [])
        self.discovered_power_consumption = entry.data.get(CONF_DISCOVERED_POWER_CONSUMPTION, [])
        self.discovered_intrusion = entry.data.get(CONF_DISCOVERED_INTRUSION, [])
        self.discovered_battery = entry.data.get(CONF_DISCOVERED_BATTERY, [])
        self.discovered_processors = entry.data.get(CONF_DISCOVERED_PROCESSORS, [])

        # Initialize SNMP objects (these will be created later to avoid blocking I/O during init)
        self.engine = None
        self.auth_data = None
        self.transport_target = None
        self.context_data = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure SNMP objects are initialized.
        
        This method initializes SNMP objects on first use to avoid blocking
        I/O operations during __init__, which can cause stability issues in
        Home Assistant's event loop.
        """
        if self._initialized:
            return

        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run the blocking SNMP initialization in an executor to avoid blocking the event loop
        def _init_snmp():
            self.engine = SnmpEngine()
            self.auth_data = _create_auth_data(self.entry)
            self.transport_target = UdpTransportTarget((self.host, self.snmp_port), timeout=5, retries=1)
            self.context_data = ContextData()
        
        await loop.run_in_executor(None, _init_snmp)
        self._initialized = True

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information via SNMP for device registry.
        
        Retrieves basic system information using SNMP OIDs including
        system model, service tag, and BIOS version to populate the
        Home Assistant device registry.
        
        Returns:
            Dictionary containing device information or fallback values
            if SNMP queries fail.
        """
        await self._ensure_initialized()
        
        try:
            model_oid = IDRAC_OIDS["system_model"]
            service_tag_oid = IDRAC_OIDS["system_service_tag"]
            bios_version_oid = IDRAC_OIDS["system_bios_version"]
            
            model = await self.get_string(model_oid)
            service_tag = await self.get_string(service_tag_oid)
            bios_version = await self.get_string(bios_version_oid)
            
            device_info = {}
            
            if model:
                device_info["model"] = model
                device_info["name"] = f"Dell {model} ({self.host})"
            else:
                device_info["model"] = "iDRAC"
                device_info["name"] = f"Dell iDRAC ({self.host})"
            
            if service_tag:
                device_info["serial_number"] = service_tag
            
            if bios_version:
                device_info["sw_version"] = f"BIOS {bios_version}"
                
            return device_info
            
        except Exception as exc:
            _LOGGER.debug("Could not fetch SNMP device info: %s", exc)
            return {
                "model": "iDRAC",
                "name": f"Dell iDRAC ({self.host})"
            }

    async def get_sensor_data(self) -> dict[str, Any]:
        """Collect all sensor data via SNMP using discovered sensor indices.
        
        Iterates through all discovered sensor indices and collects data for
        each sensor type. The sensor indices are discovered during integration
        setup and stored in the configuration entry.
        
        Returns:
            Dictionary containing organized sensor data with keys:
            - temperatures: CPU temperature readings with status
            - fans: Fan RPM readings with status
            - power_supplies: PSU status and power metrics
            - voltages: Voltage probe readings (filtered)
            - memory: Memory module status and size
            - power_consumption: System power consumption data
        """
        await self._ensure_initialized()
        
        data = {
            "temperatures": {},
            "fans": {},
            "power_supplies": {},
            "voltages": {},
            "memory": {},
            "virtual_disks": {},
            "physical_disks": {},
            "storage_controllers": {},
            "system_voltages": {},
            "power_consumption": {},
            "intrusion_detection": {},
            "battery": {},
            "processors": {},
        }

        # Get CPU temperature sensors
        for cpu_id in self.discovered_cpus:
            temp_reading = await self.get_value(IDRAC_OIDS["temp_probe_reading"].format(index=cpu_id))
            temp_status = await self.get_value(IDRAC_OIDS["temp_probe_status"].format(index=cpu_id))
            temp_location = await self.get_string(IDRAC_OIDS["temp_probe_location"].format(index=cpu_id))
            temp_upper_critical = await self.get_value(IDRAC_OIDS["temp_probe_upper_critical"].format(index=cpu_id))
            temp_upper_warning = await self.get_value(IDRAC_OIDS["temp_probe_upper_warning"].format(index=cpu_id))

            if temp_reading is not None:
                # Convert temperature from tenths of degrees to degrees
                temperature_celsius = temp_reading / 10.0 if temp_reading > 100 else temp_reading
                
                data["temperatures"][f"cpu_temp_{cpu_id}"] = {
                    "name": temp_location or f"CPU {cpu_id} Temperature",
                    "temperature": temperature_celsius,
                    "status": TEMP_STATUS.get(temp_status, "unknown"),
                    "upper_threshold_critical": temp_upper_critical / 10.0 if temp_upper_critical and temp_upper_critical > 100 else temp_upper_critical,
                    "upper_threshold_non_critical": temp_upper_warning / 10.0 if temp_upper_warning and temp_upper_warning > 100 else temp_upper_warning,
                }

        # Get fan sensors
        for fan_id in self.discovered_fans:
            fan_reading = await self.get_value(IDRAC_OIDS["cooling_device_reading"].format(index=fan_id))
            fan_status = await self.get_value(IDRAC_OIDS["cooling_device_status"].format(index=fan_id))
            fan_location = await self.get_string(IDRAC_OIDS["cooling_device_location"].format(index=fan_id))

            if fan_reading is not None:
                data["fans"][f"fan_{fan_id}"] = {
                    "name": fan_location or f"Fan {fan_id}",
                    "speed_rpm": fan_reading,
                    "status": FAN_STATUS.get(fan_status, "unknown"),
                }

        # Get PSU sensors
        for psu_id in self.discovered_psus:
            psu_status = await self.get_value(IDRAC_OIDS["psu_status"].format(index=psu_id))
            psu_location = await self.get_string(IDRAC_OIDS["psu_location"].format(index=psu_id))
            psu_max_output = await self.get_value(IDRAC_OIDS["psu_max_output"].format(index=psu_id))
            psu_current_output = await self.get_value(IDRAC_OIDS["psu_current_output"].format(index=psu_id))

            # Only add PSU sensors that have valid status data
            if psu_status is not None and psu_location:
                data["power_supplies"][f"psu_{psu_id}"] = {
                    "name": psu_location,
                    "status": PSU_STATUS.get(psu_status, "unknown"),
                    "power_capacity_watts": psu_max_output,
                    "power_output_watts": psu_current_output,
                }
                _LOGGER.debug("Added PSU sensor %d: %s (status=%s)", 
                            psu_id, psu_location, psu_status)
            else:
                _LOGGER.debug("Skipped PSU sensor %d: status=%s, location=%s", 
                            psu_id, psu_status, psu_location)

        # Get voltage probe sensors
        for voltage_id in self.discovered_voltage_probes:
            voltage_reading = await self.get_value(IDRAC_OIDS["psu_input_voltage"].format(index=voltage_id))
            voltage_location = await self.get_string(IDRAC_OIDS["psu_location"].format(index=voltage_id))

            if voltage_reading is not None:
                # Convert millivolts to volts
                voltage_volts = voltage_reading / 1000.0 if voltage_reading > 1000 else voltage_reading
                
                data["voltages"][f"psu_voltage_{voltage_id}"] = {
                    "name": f"{voltage_location} Voltage" if voltage_location else f"PSU {voltage_id} Voltage",
                    "reading_volts": voltage_volts,
                    "status": "ok",
                }

        # Get memory sensors
        for memory_id in self.discovered_memory:
            memory_status = await self.get_value(IDRAC_OIDS["memory_status"].format(index=memory_id))
            memory_location = await self.get_string(IDRAC_OIDS["memory_location"].format(index=memory_id))
            memory_size = await self.get_value(IDRAC_OIDS["memory_size"].format(index=memory_id))

            # Only add memory sensors that have valid status data
            if memory_status is not None and memory_location:
                data["memory"][f"memory_{memory_id}"] = {
                    "name": memory_location,
                    "status": MEMORY_HEALTH_STATUS.get(memory_status, "unknown"),
                    "size_kb": memory_size,
                }
                _LOGGER.debug("Added memory sensor %d: %s (status=%s, size=%s)", 
                            memory_id, memory_location, memory_status, memory_size)
            else:
                _LOGGER.debug("Skipped memory sensor %d: status=%s, location=%s", 
                            memory_id, memory_status, memory_location)

        # Get power consumption
        if self.discovered_power_consumption:
            power_current = await self.get_value(IDRAC_OIDS["power_consumption_current"])
            power_peak = await self.get_value(IDRAC_OIDS["power_consumption_peak"])

            if power_current is not None:
                data["power_consumption"] = {
                    "consumed_watts": power_current,
                    "max_consumed_watts": power_peak,
                }

        # Get intrusion detection sensors
        for intrusion_id in self.discovered_intrusion:
            intrusion_reading = await self.get_value(IDRAC_OIDS["intrusion_reading"].format(index=intrusion_id))
            intrusion_status = await self.get_value(IDRAC_OIDS["intrusion_status"].format(index=intrusion_id))
            intrusion_location = await self.get_string(IDRAC_OIDS["intrusion_location"].format(index=intrusion_id))

            if intrusion_reading is not None and intrusion_location:
                data["intrusion_detection"][f"intrusion_{intrusion_id}"] = {
                    "name": intrusion_location,
                    "reading": intrusion_reading,
                    "status": INTRUSION_STATUS.get(intrusion_status, "unknown"),
                }
                _LOGGER.debug("Added intrusion sensor %d: %s (reading=%s, status=%s)", 
                            intrusion_id, intrusion_location, intrusion_reading, intrusion_status)

        # Get battery sensors
        for battery_id in self.discovered_battery:
            battery_reading = await self.get_value(IDRAC_OIDS["battery_reading"].format(index=battery_id))
            battery_status = await self.get_value(IDRAC_OIDS["battery_status"].format(index=battery_id))

            if battery_reading is not None and battery_status is not None:
                data["battery"][f"battery_{battery_id}"] = {
                    "name": f"System Battery {battery_id}",
                    "reading": battery_reading,
                    "status": BATTERY_STATUS.get(battery_status, "unknown"),
                }
                _LOGGER.debug("Added battery sensor %d: reading=%s, status=%s", 
                            battery_id, battery_reading, battery_status)

        # Get processor sensors
        for processor_id in self.discovered_processors:
            processor_reading = await self.get_value(IDRAC_OIDS["processor_reading"].format(index=processor_id))
            processor_status = await self.get_value(IDRAC_OIDS["processor_status"].format(index=processor_id))
            processor_location = await self.get_string(IDRAC_OIDS["processor_location"].format(index=processor_id))

            if processor_reading is not None and processor_location:
                data["processors"][f"processor_{processor_id}"] = {
                    "name": processor_location,
                    "reading": processor_reading,
                    "status": PROCESSOR_STATUS.get(processor_status, "unknown"),
                }
                _LOGGER.debug("Added processor sensor %d: %s (reading=%s, status=%s)", 
                            processor_id, processor_location, processor_reading, processor_status)

        return data

    async def get_value(self, oid: str) -> int | None:
        """Get an SNMP value and return as integer.
        
        Performs an SNMP GET operation for the specified OID and converts
        the result to an integer. Handles errors gracefully and returns
        None if the value cannot be retrieved or converted.
        
        Args:
            oid: SNMP Object Identifier string.
            
        Returns:
            Integer value from SNMP or None if retrieval/conversion fails.
        """
        await self._ensure_initialized()
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication:
                _LOGGER.debug("SNMP error indication for OID %s: %s", oid, error_indication)
                return None
            elif error_status:
                _LOGGER.debug("SNMP error status for OID %s: %s", oid, error_status.prettyPrint())
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        _LOGGER.debug("Could not convert SNMP value to int for OID %s: %s", oid, val)
                        return None
            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP value for OID %s: %s", oid, exc)
            return None

    async def get_string(self, oid: str) -> str | None:
        """Get an SNMP value and return as string.
        
        Performs an SNMP GET operation for the specified OID and converts
        the result to a string. Strips whitespace and handles errors gracefully.
        
        Args:
            oid: SNMP Object Identifier string.
            
        Returns:
            String value from SNMP or None if retrieval fails.
        """
        await self._ensure_initialized()
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication:
                _LOGGER.debug("SNMP error indication for OID %s: %s", oid, error_indication)
                return None
            elif error_status:
                _LOGGER.debug("SNMP error status for OID %s: %s", oid, error_status.prettyPrint())
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    return str(val).strip()
            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP string for OID %s: %s", oid, exc)
            return None