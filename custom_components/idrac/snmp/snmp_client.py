"""Dell iDRAC SNMP client."""
from __future__ import annotations

import asyncio
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
        self.snmp_port = int(entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT))
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

        loop = asyncio.get_event_loop()
        
        # Run the blocking SNMP initialization in an executor to avoid blocking the event loop
        def _init_snmp():
            self.engine = SnmpEngine()
            self.auth_data = _create_auth_data(self.entry)
            # Optimize SNMP transport with faster timeouts and no retries for speed
            self.transport_target = UdpTransportTarget((self.host, self.snmp_port), timeout=2, retries=0)
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
        
        Uses concurrent SNMP requests to optimize performance and reduce
        update times. Collects data for all sensor types in parallel.
        
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

        # Collect all SNMP requests concurrently for better performance
        
        # Build concurrent tasks for all sensors
        tasks = []
        
        # Temperature sensor tasks
        for cpu_id in self.discovered_cpus:
            tasks.extend([
                self._get_temperature_data(cpu_id),
            ])
        
        # Fan sensor tasks  
        for fan_id in self.discovered_fans:
            tasks.extend([
                self._get_fan_data(fan_id),
            ])
            
        # PSU sensor tasks
        for psu_id in self.discovered_psus:
            tasks.extend([
                self._get_psu_data(psu_id),
            ])
            
        # Execute all requests concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, dict) and not isinstance(result, Exception):
                    if "temperature" in result:
                        data["temperatures"].update(result["temperature"])
                    elif "fan" in result:
                        data["fans"].update(result["fan"])
                    elif "psu" in result:
                        data["power_supplies"].update(result["psu"])
        
        # Handle remaining sensors sequentially for now (can be optimized later)
        await self._collect_remaining_sensors(data)
        
        return data
    
    async def _get_temperature_data(self, cpu_id: int) -> dict[str, Any]:
        """Get temperature data for a specific CPU concurrently."""
        try:
            temp_reading, temp_status, temp_location, temp_upper_critical, temp_upper_warning = await asyncio.gather(
                self.get_value(IDRAC_OIDS["temp_probe_reading"].format(index=cpu_id)),
                self.get_value(IDRAC_OIDS["temp_probe_status"].format(index=cpu_id)),
                self.get_string(IDRAC_OIDS["temp_probe_location"].format(index=cpu_id)),
                self.get_value(IDRAC_OIDS["temp_probe_upper_critical"].format(index=cpu_id)),
                self.get_value(IDRAC_OIDS["temp_probe_upper_warning"].format(index=cpu_id)),
                return_exceptions=True
            )
            
            if temp_reading is not None and not isinstance(temp_reading, Exception):
                temperature_celsius = temp_reading / 10.0 if temp_reading > 100 else temp_reading
                
                return {"temperature": {
                    f"cpu_temp_{cpu_id}": {
                        "name": temp_location if not isinstance(temp_location, Exception) else f"CPU {cpu_id} Temperature",
                        "temperature": temperature_celsius,
                        "status": TEMP_STATUS.get(temp_status if not isinstance(temp_status, Exception) else None, "unknown"),
                        "upper_threshold_critical": temp_upper_critical / 10.0 if temp_upper_critical and temp_upper_critical > 100 and not isinstance(temp_upper_critical, Exception) else temp_upper_critical,
                        "upper_threshold_non_critical": temp_upper_warning / 10.0 if temp_upper_warning and temp_upper_warning > 100 and not isinstance(temp_upper_warning, Exception) else temp_upper_warning,
                    }
                }}
        except Exception:
            pass
        return {}
    
    async def _get_fan_data(self, fan_id: int) -> dict[str, Any]:
        """Get fan data for a specific fan concurrently."""
        try:
            fan_reading, fan_status, fan_location = await asyncio.gather(
                self.get_value(IDRAC_OIDS["cooling_device_reading"].format(index=fan_id)),
                self.get_value(IDRAC_OIDS["cooling_device_status"].format(index=fan_id)),
                self.get_string(IDRAC_OIDS["cooling_device_location"].format(index=fan_id)),
                return_exceptions=True
            )
            
            if fan_reading is not None and not isinstance(fan_reading, Exception):
                return {"fan": {
                    f"fan_{fan_id}": {
                        "name": fan_location if not isinstance(fan_location, Exception) else f"Fan {fan_id}",
                        "speed_rpm": fan_reading,
                        "status": FAN_STATUS.get(fan_status if not isinstance(fan_status, Exception) else None, "unknown"),
                    }
                }}
        except Exception:
            pass
        return {}
        
    async def _get_psu_data(self, psu_id: int) -> dict[str, Any]:
        """Get PSU data for a specific PSU concurrently."""
        try:
            psu_status, psu_location, psu_max_output, psu_current_output = await asyncio.gather(
                self.get_value(IDRAC_OIDS["psu_status"].format(index=psu_id)),
                self.get_string(IDRAC_OIDS["psu_location"].format(index=psu_id)),
                self.get_value(IDRAC_OIDS["psu_max_output"].format(index=psu_id)),
                self.get_value(IDRAC_OIDS["psu_current_output"].format(index=psu_id)),
                return_exceptions=True
            )
            
            if psu_status is not None and not isinstance(psu_status, Exception) and psu_location and not isinstance(psu_location, Exception):
                return {"psu": {
                    f"psu_{psu_id}": {
                        "name": psu_location,
                        "status": PSU_STATUS.get(psu_status, "unknown"),
                        "power_capacity_watts": psu_max_output if not isinstance(psu_max_output, Exception) else None,
                        "power_output_watts": psu_current_output if not isinstance(psu_current_output, Exception) else None,
                    }
                }}
        except Exception:
            pass
        return {}
    
    async def _collect_remaining_sensors(self, data: dict[str, Any]) -> None:
        """Collect remaining sensor types that aren't optimized yet."""
        # Collect other sensors with minimal overhead
        tasks = []
        
        # Voltage probe sensors
        for voltage_id in self.discovered_voltage_probes:
            tasks.append(self._get_voltage_data(voltage_id))
            
        # Memory sensors  
        for memory_id in self.discovered_memory:
            tasks.append(self._get_memory_data(memory_id))
            
        # Power consumption (if discovered)
        if self.discovered_power_consumption:
            tasks.append(self._get_power_consumption_data())
            
        # Execute remaining sensors concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict) and not isinstance(result, Exception):
                    for key, value in result.items():
                        if key in data:
                            data[key].update(value)
    
    async def _get_voltage_data(self, voltage_id: int) -> dict[str, Any]:
        """Get voltage data concurrently."""
        try:
            voltage_reading, voltage_location = await asyncio.gather(
                self.get_value(IDRAC_OIDS["psu_input_voltage"].format(index=voltage_id)),
                self.get_string(IDRAC_OIDS["psu_location"].format(index=voltage_id)),
                return_exceptions=True
            )
            
            if voltage_reading is not None and not isinstance(voltage_reading, Exception):
                voltage_volts = voltage_reading / 1000.0 if voltage_reading > 1000 else voltage_reading
                return {"voltages": {
                    f"psu_voltage_{voltage_id}": {
                        "name": f"{voltage_location} Voltage" if not isinstance(voltage_location, Exception) and voltage_location else f"PSU {voltage_id} Voltage",
                        "reading_volts": voltage_volts,
                        "status": "ok",
                    }
                }}
        except Exception:
            pass
        return {}
    
    async def _get_memory_data(self, memory_id: int) -> dict[str, Any]:
        """Get memory data concurrently."""
        try:
            memory_status, memory_location, memory_size = await asyncio.gather(
                self.get_value(IDRAC_OIDS["memory_status"].format(index=memory_id)),
                self.get_string(IDRAC_OIDS["memory_location"].format(index=memory_id)),
                self.get_value(IDRAC_OIDS["memory_size"].format(index=memory_id)),
                return_exceptions=True
            )
            
            if (memory_status is not None and not isinstance(memory_status, Exception) and 
                memory_location and not isinstance(memory_location, Exception)):
                return {"memory": {
                    f"memory_{memory_id}": {
                        "name": memory_location,
                        "status": MEMORY_HEALTH_STATUS.get(memory_status, "unknown"),
                        "size_kb": memory_size if not isinstance(memory_size, Exception) else None,
                    }
                }}
        except Exception:
            pass
        return {}
    
    async def _get_power_consumption_data(self) -> dict[str, Any]:
        """Get power consumption data concurrently."""
        try:
            power_current, power_peak = await asyncio.gather(
                self.get_value(IDRAC_OIDS["power_consumption_current"]),
                self.get_value(IDRAC_OIDS["power_consumption_peak"]),
                return_exceptions=True
            )
            
            if power_current is not None and not isinstance(power_current, Exception):
                return {"power_consumption": {
                    "consumed_watts": power_current,
                    "max_consumed_watts": power_peak if not isinstance(power_peak, Exception) else None,
                }}
        except Exception:
            pass
        return {}

    async def get_value(self, oid: str) -> int | None:
        """Get an SNMP value and return as integer.
        
        Optimized for performance with minimal logging overhead.
        
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

            if error_indication or error_status:
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return None
            return None

        except Exception:
            return None

    async def get_string(self, oid: str) -> str | None:
        """Get an SNMP value and return as string.
        
        Optimized for performance with minimal logging overhead.
        
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

            if error_indication or error_status:
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    return str(val).strip()
            return None

        except Exception:
            return None