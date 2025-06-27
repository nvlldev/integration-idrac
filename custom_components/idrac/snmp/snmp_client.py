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
    setCmd,
)
from pysnmp.proto.rfc1902 import Integer as SnmpInteger
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
)
from .snmp_processor import SNMPDataProcessor

_LOGGER = logging.getLogger(__name__)


def _create_auth_data(entry: ConfigEntry) -> CommunityData | UsmUserData:
    """Create the appropriate authentication data for SNMP."""
    snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
    _LOGGER.debug("Creating auth data for SNMP version: %s", snmp_version)
    
    try:
        if snmp_version == "v3":
            username = entry.data.get(CONF_USERNAME, "")
            auth_protocol = entry.data.get(CONF_AUTH_PROTOCOL, "none")
            auth_password = entry.data.get(CONF_AUTH_PASSWORD, "")
            priv_protocol = entry.data.get(CONF_PRIV_PROTOCOL, "none")
            priv_password = entry.data.get(CONF_PRIV_PASSWORD, "")
            
            _LOGGER.debug("SNMPv3 parameters: username=%s, auth_protocol=%s, priv_protocol=%s", 
                         username, auth_protocol, priv_protocol)
            
            # Map protocol names to pysnmp protocol objects
            auth_proto = None
            if auth_protocol != "none":
                auth_proto = getattr(rfc1902, SNMP_AUTH_PROTOCOLS[auth_protocol], None)
                _LOGGER.debug("Auth protocol mapped to: %s", auth_proto)
            
            priv_proto = None
            if priv_protocol != "none":
                priv_proto = getattr(rfc1902, SNMP_PRIV_PROTOCOLS[priv_protocol], None)
                _LOGGER.debug("Priv protocol mapped to: %s", priv_proto)
            
            user_data = UsmUserData(
                userName=username,
                authKey=auth_password if auth_proto else None,
                privKey=priv_password if priv_proto else None,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )
            _LOGGER.debug("Created UsmUserData for user: %s", username)
            return user_data
        else:
            # SNMP v2c
            community = entry.data.get(CONF_COMMUNITY, "public")
            _LOGGER.debug("Creating CommunityData for community: %s", community)
            community_data = CommunityData(community)
            _LOGGER.debug("Created CommunityData successfully")
            return community_data
    except Exception as exc:
        _LOGGER.error("Error creating SNMP auth data: %s", exc, exc_info=True)
        raise


class SNMPClient:
    """Dell iDRAC SNMP client for sensor data collection.
    
    This client handles all SNMP operations for Dell iDRAC devices using pysnmp.
    It supports both SNMPv2c and SNMPv3 authentication, manages discovered sensor
    indices, and provides methods for collecting comprehensive sensor data.
    
    The client collects data for:
    - CPU temperature sensors
    - Cooling device (fan) sensors  
    - Power supply status and metrics
    - Memory module information
    - Voltage probe readings
    - System power consumption
    - Chassis intrusion detection
    - Battery status
    - Processor information
    """

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the SNMP client with configuration from Home Assistant.
        
        Args:
            entry: Home Assistant configuration entry containing SNMP parameters
        """
        _LOGGER.debug("Initializing SNMPClient")
        
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)
        
        _LOGGER.debug("SNMP client host: %s, port: %d", self.host, self.port)
        
        # SNMP connection objects (initialized on first use)
        self.engine = None
        self.auth_data = None
        self.transport_target = None
        self.context_data = None
        
        # Load discovered sensor indices from config
        self.discovered_cpus = entry.data.get(CONF_DISCOVERED_CPUS, [])
        self.discovered_fans = entry.data.get(CONF_DISCOVERED_FANS, [])
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
        
        sensor_count = self._count_discovered_sensors()
        _LOGGER.debug("SNMP client initialized for %s:%d with %d discovered sensor types", 
                     self.host, self.port, sensor_count)
        
        # Log sensor breakdown for debugging
        _LOGGER.debug("Discovered sensors breakdown: CPUs=%d, Fans=%d, PSUs=%d, Memory=%d, VoltageProbes=%d",
                     len(self.discovered_cpus), len(self.discovered_fans), len(self.discovered_psus),
                     len(self.discovered_memory), len(self.discovered_voltage_probes))

    def _count_discovered_sensors(self) -> int:
        """Count total discovered sensors across all categories."""
        return (len(self.discovered_cpus) + len(self.discovered_fans) + 
                len(self.discovered_psus) + len(self.discovered_voltage_probes) + 
                len(self.discovered_memory) + len(self.discovered_virtual_disks) +
                len(self.discovered_physical_disks) + len(self.discovered_storage_controllers) +
                len(self.discovered_detailed_memory) + len(self.discovered_system_voltages) +
                len(self.discovered_intrusion) + len(self.discovered_battery) +
                len(self.discovered_processors) + (1 if self.discovered_power_consumption else 0))

    async def _ensure_initialized(self) -> None:
        """Ensure SNMP connection objects are initialized."""
        if self.engine is None:
            _LOGGER.debug("Initializing SNMP engine for %s:%d", self.host, self.port)
            
            try:
                _LOGGER.debug("Creating SnmpEngine...")
                self.engine = SnmpEngine()
                _LOGGER.debug("SnmpEngine created successfully")
                
                _LOGGER.debug("Creating auth data...")
                self.auth_data = _create_auth_data(self.entry)
                _LOGGER.debug("Auth data created: %s", type(self.auth_data).__name__)
                
                _LOGGER.debug("Creating transport target...")
                _LOGGER.debug("Transport target parameters: host=%s (type: %s), port=%s (type: %s)", 
                             self.host, type(self.host).__name__, self.port, type(self.port).__name__)
                
                # Ensure port is an integer
                if not isinstance(self.port, int):
                    try:
                        port_int = int(self.port)
                        _LOGGER.debug("Converted port from %s to %d", self.port, port_int)
                        self.port = port_int
                    except (ValueError, TypeError) as exc:
                        _LOGGER.error("Invalid port value: %s (type: %s): %s", self.port, type(self.port).__name__, exc)
                        raise ValueError(f"Invalid SNMP port: {self.port}") from exc
                
                # Ensure host is a string
                if not isinstance(self.host, str):
                    _LOGGER.error("Invalid host value: %s (type: %s)", self.host, type(self.host).__name__)
                    raise ValueError(f"Invalid SNMP host: {self.host}")
                
                # Validate values before creating transport target
                if not self.host or not self.host.strip():
                    raise ValueError("SNMP host is empty or whitespace")
                if self.port <= 0 or self.port > 65535:
                    raise ValueError(f"SNMP port {self.port} is out of valid range (1-65535)")
                
                _LOGGER.debug("Creating UdpTransportTarget with validated parameters: ('%s', %d)", self.host, self.port)
                
                try:
                    self.transport_target = UdpTransportTarget((self.host, self.port), timeout=3.0, retries=2)
                    _LOGGER.debug("Transport target created successfully for %s:%d", self.host, self.port)
                except Exception as transport_exc:
                    _LOGGER.error("Failed to create UdpTransportTarget: %s", transport_exc, exc_info=True)
                    _LOGGER.error("Transport parameters were: host='%s' (len=%d), port=%d", 
                                self.host, len(self.host) if self.host else 0, self.port)
                    raise
                
                _LOGGER.debug("Creating context data...")
                self.context_data = ContextData()
                _LOGGER.debug("Context data created successfully")
                
                # Verify all components are properly initialized
                if self.engine is None:
                    raise RuntimeError("SnmpEngine is None after creation")
                if self.auth_data is None:
                    raise RuntimeError("auth_data is None after creation")
                if self.transport_target is None:
                    raise RuntimeError("transport_target is None after creation")
                if self.context_data is None:
                    raise RuntimeError("context_data is None after creation")
                
                _LOGGER.info("SNMP engine initialized successfully for %s:%d", self.host, self.port)
            except Exception as exc:
                _LOGGER.error("Failed to initialize SNMP components: %s", exc, exc_info=True)
                # Reset all components on failure
                self.engine = None
                self.auth_data = None
                self.transport_target = None
                self.context_data = None
                raise

    async def close(self) -> None:
        """Close the SNMP client and cleanup resources."""
        if self.engine:
            self.engine.transportDispatcher.closeDispatcher()
            _LOGGER.debug("SNMP client closed for %s:%d", self.host, self.port)

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information via SNMP for device registry.
        
        Returns:
            Dictionary containing device information like model, service tag, etc.
        """
        _LOGGER.debug("SNMPClient.get_device_info() called for %s:%d", self.host, self.port)
        
        try:
            await self._ensure_initialized()
            _LOGGER.debug("SNMP client initialized successfully")
        except Exception as exc:
            _LOGGER.error("Failed to initialize SNMP client: %s", exc, exc_info=True)
            return {"name": f"Dell iDRAC ({self.host})"}
        
        device_info = {}
        
        # Get system information via SNMP with individual error handling for each OID
        system_model = None
        try:
            _LOGGER.debug("Fetching system model via SNMP OID: %s", IDRAC_OIDS["system_model"])
            system_model = await self.get_string(IDRAC_OIDS["system_model"])
            _LOGGER.debug("System model: %s", system_model)
        except Exception as exc:
            _LOGGER.error("Failed to get system model via SNMP: %s", exc, exc_info=True)
            
        service_tag = None
        try:
            _LOGGER.debug("Fetching service tag via SNMP OID: %s", IDRAC_OIDS["system_service_tag"])
            service_tag = await self.get_string(IDRAC_OIDS["system_service_tag"])
            _LOGGER.debug("Service tag: %s", service_tag)
        except Exception as exc:
            _LOGGER.warning("Failed to get service tag via SNMP: %s", exc)
            
        bios_version = None
        try:
            _LOGGER.debug("Fetching BIOS version via SNMP OID: %s", IDRAC_OIDS["system_bios_version"])
            bios_version = await self.get_string(IDRAC_OIDS["system_bios_version"])
            _LOGGER.debug("BIOS version: %s", bios_version)
        except Exception as exc:
            _LOGGER.warning("Failed to get BIOS version via SNMP: %s", exc)
        
        # Build device info from successfully retrieved values
        if system_model:
            device_info["model"] = system_model
            device_info["name"] = f"Dell {system_model} ({self.host})"
        else:
            device_info["name"] = f"Dell iDRAC ({self.host})"
            
        if service_tag:
            device_info["serial_number"] = service_tag
            
        if bios_version:
            device_info["sw_version"] = bios_version
            
        _LOGGER.debug("Retrieved device info via SNMP: %s", device_info)
        return device_info

    async def set_snmp_value(self, oid: str, value: int) -> bool:
        """Set an SNMP value using SET command.
        
        Args:
            oid: SNMP OID to set
            value: Integer value to set
            
        Returns:
            True if the operation was successful, False otherwise.
        """
        await self._ensure_initialized()
        
        try:
            error_indication, error_status, error_index, var_binds = await setCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid), SnmpInteger(value)),
            )

            if error_indication:
                _LOGGER.error("SNMP SET error indication for OID %s: %s", oid, error_indication)
                return False
                
            if error_status:
                _LOGGER.error("SNMP SET error status for OID %s: %s at %s", 
                             oid, error_status.prettyPrint(), 
                             error_index and var_binds[int(error_index) - 1][0] or '?')
                return False
                
            _LOGGER.debug("Successfully set SNMP value for OID %s to %s", oid, value)
            return True
            
        except Exception as exc:
            _LOGGER.error("Exception during SNMP SET for OID %s: %s", oid, exc)
            return False

    async def get_sensor_data(self) -> dict[str, Any]:
        """Collect comprehensive sensor data from the Dell iDRAC device.
        
        Returns:
            Dictionary containing organized sensor data by category.
        """
        start_time = __import__('time').time()
        total_sensors = self._count_discovered_sensors()
        
        _LOGGER.debug("Starting SNMP data collection for %d sensors from %s:%d", 
                     total_sensors, self.host, self.port)
        
        # Initialize data structure
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
        
        try:
            await self._ensure_initialized()
            
            # Verify initialization was successful before proceeding
            if self.context_data is None:
                _LOGGER.error("SNMP initialization failed - context_data is None")
                return data
            
            _LOGGER.debug("SNMP initialization successful, proceeding with data collection")
            
            # Collect all OIDs to query
            all_value_oids = []
            all_string_oids = []
            
            # Temperature probe OIDs
            for cpu_id in self.discovered_cpus:
                all_value_oids.extend([
                    IDRAC_OIDS["temp_probe_reading"].format(index=cpu_id),
                    IDRAC_OIDS["temp_probe_status"].format(index=cpu_id),
                    IDRAC_OIDS["temp_probe_upper_critical"].format(index=cpu_id),
                    IDRAC_OIDS["temp_probe_upper_warning"].format(index=cpu_id),
                ])
                all_string_oids.append(IDRAC_OIDS["temp_probe_location"].format(index=cpu_id))
                
            # Cooling device (fan) OIDs
            for fan_id in self.discovered_fans:
                all_value_oids.extend([
                    IDRAC_OIDS["cooling_device_reading"].format(index=fan_id),
                    IDRAC_OIDS["cooling_device_status"].format(index=fan_id),
                ])
                all_string_oids.append(IDRAC_OIDS["cooling_device_location"].format(index=fan_id))
                
            # PSU OIDs
            for psu_id in self.discovered_psus:
                all_value_oids.extend([
                    IDRAC_OIDS["psu_status"].format(index=psu_id),
                    IDRAC_OIDS["psu_max_output"].format(index=psu_id),
                    IDRAC_OIDS["psu_current_output"].format(index=psu_id),
                ])
                all_string_oids.append(IDRAC_OIDS["psu_location"].format(index=psu_id))
                
            # Memory OIDs
            for memory_id in self.discovered_memory:
                all_value_oids.extend([
                    IDRAC_OIDS["memory_status"].format(index=memory_id),
                    IDRAC_OIDS["memory_size"].format(index=memory_id),
                ])
                all_string_oids.append(IDRAC_OIDS["memory_location"].format(index=memory_id))
            
            # Voltage probe OIDs
            for voltage_id in self.discovered_voltage_probes:
                all_value_oids.append(IDRAC_OIDS["psu_input_voltage"].format(index=voltage_id))
                all_string_oids.append(IDRAC_OIDS["psu_location"].format(index=voltage_id))
                
            # Power consumption OIDs
            if self.discovered_power_consumption:
                all_value_oids.extend([
                    IDRAC_OIDS["power_consumption_current"],
                    IDRAC_OIDS["power_consumption_peak"],
                ])
                
            # Intrusion detection OIDs
            for intrusion_id in self.discovered_intrusion:
                all_value_oids.extend([
                    IDRAC_OIDS["intrusion_reading"].format(index=intrusion_id),
                    IDRAC_OIDS["intrusion_status"].format(index=intrusion_id),
                ])
                all_string_oids.append(IDRAC_OIDS["intrusion_location"].format(index=intrusion_id))
                
            # Battery OIDs
            for battery_id in self.discovered_battery:
                all_value_oids.extend([
                    IDRAC_OIDS["battery_reading"].format(index=battery_id),
                    IDRAC_OIDS["battery_status"].format(index=battery_id),
                ])
                
            # Processor OIDs
            for processor_id in self.discovered_processors:
                all_value_oids.extend([
                    IDRAC_OIDS["processor_reading"].format(index=processor_id),
                    IDRAC_OIDS["processor_status"].format(index=processor_id),
                ])
                all_string_oids.append(IDRAC_OIDS["processor_location"].format(index=processor_id))
                
            # Get ALL data using parallel bulk operations for improved performance
            _LOGGER.debug("Collecting %d value OIDs and %d string OIDs", len(all_value_oids), len(all_string_oids))
            
            # Run both bulk operations in parallel to improve performance
            tasks = []
            if all_value_oids:
                tasks.append(self._bulk_get_values(all_value_oids))
            else:
                tasks.append(asyncio.create_task(asyncio.sleep(0, result={})))
                
            if all_string_oids:
                tasks.append(self._bulk_get_strings(all_string_oids))
            else:
                tasks.append(asyncio.create_task(asyncio.sleep(0, result={})))
            
            try:
                _LOGGER.debug("Starting parallel bulk collection")
                values, strings = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Handle any exceptions from parallel execution
                if isinstance(values, Exception):
                    _LOGGER.warning("Bulk SNMP values collection failed: %s", values)
                    values = {}
                if isinstance(strings, Exception):
                    _LOGGER.warning("Bulk SNMP strings collection failed: %s", strings)
                    strings = {}
                    
                _LOGGER.debug("Parallel bulk collection completed: %d values, %d strings", len(values), len(strings))
            except Exception as exc:
                _LOGGER.warning("Parallel bulk SNMP collection failed: %s", exc)
                values = {}
                strings = {}
                
            bulk_success = len(values) > 0 or len(strings) > 0
            if bulk_success:
                _LOGGER.debug("Bulk SNMP collection successful: %d values, %d strings", len(values), len(strings))
            else:
                _LOGGER.warning("Bulk SNMP collection returned no data - network or authentication issue?")
                
            # Create data processor with discovered sensor indices
            discovered_sensors = {
                'cpus': self.discovered_cpus,
                'fans': self.discovered_fans,
                'psus': self.discovered_psus,
                'voltage_probes': self.discovered_voltage_probes,
                'memory': self.discovered_memory,
                'virtual_disks': self.discovered_virtual_disks,
                'physical_disks': self.discovered_physical_disks,
                'storage_controllers': self.discovered_storage_controllers,
                'detailed_memory': self.discovered_detailed_memory,
                'system_voltages': self.discovered_system_voltages,
                'power_consumption': self.discovered_power_consumption,
                'intrusion': self.discovered_intrusion,
                'battery': self.discovered_battery,
                'processors': self.discovered_processors,
            }
            
            processor = SNMPDataProcessor(discovered_sensors)
            data = processor.process_snmp_data(values, strings)
                    
        except Exception as exc:
            _LOGGER.error("Critical SNMP error during bulk data collection: %s", exc)
            # Return empty data structure on failure
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
        
        # Generate summary of collected data
        sensor_counts = {k: len(v) for k, v in data.items() if v}
        total_collected = sum(sensor_counts.values())
        
        if start_time:
            elapsed = __import__('time').time() - start_time
            _LOGGER.debug("SNMP collection completed in %.2fs: %d sensors across %d categories", 
                         elapsed, total_collected, len(sensor_counts))
        
        if total_collected == 0:
            _LOGGER.error("No sensor data collected - check SNMP connectivity and credentials")
        elif total_collected < total_sensors * 0.8:  # Less than 80% of expected sensors
            _LOGGER.warning("Only collected %d/%d expected sensors - some may be offline", 
                           total_collected, total_sensors)
        else:
            _LOGGER.debug("Successfully collected data from %s", 
                         ", ".join(f"{count} {category.replace('_', ' ')}" for category, count in sensor_counts.items()))
        
        return data

    async def get_value(self, oid: str) -> int | None:
        """Get an SNMP value and return as integer."""
        result = await self._bulk_get_values([oid])
        return result.get(oid)

    async def get_string(self, oid: str) -> str | None:
        """Get an SNMP value and return as string."""
        _LOGGER.debug("Getting single SNMP string for OID: %s", oid)
        try:
            result = await self._bulk_get_strings([oid])
            value = result.get(oid)
            _LOGGER.debug("Retrieved string value for OID %s: %s", oid, repr(value))
            return value
        except Exception as exc:
            _LOGGER.error("Error getting SNMP string for OID %s: %s", oid, exc, exc_info=True)
            return None

    async def _bulk_get_values(self, oids: list[str]) -> dict[str, int]:
        """Get multiple SNMP values as integers using bulk operations."""
        # Don't call _ensure_initialized again if already called
        if self.context_data is None:
            _LOGGER.error("SNMP context_data is None - initialization was not successful")
            return {}
        
        if not oids:
            return {}
            
        results = {}
        
        # Process OIDs in batches of 25 for better performance
        batch_size = 25
        total_batches = (len(oids) + batch_size - 1) // batch_size
        _LOGGER.debug("Processing %d value OIDs in %d batches of %d", len(oids), total_batches, batch_size)
        
        for batch_num, i in enumerate(range(0, len(oids), batch_size), 1):
            batch_oids = oids[i:i + batch_size]
            _LOGGER.debug("Processing value batch %d/%d with %d OIDs", batch_num, total_batches, len(batch_oids))
            
            try:
                # Create ObjectType list for batch
                object_types = []
                for oid in batch_oids:
                    try:
                        object_types.append(ObjectType(ObjectIdentity(oid)))
                    except Exception as oid_exc:
                        _LOGGER.debug("Failed to create ObjectType for OID %s: %s", oid, oid_exc)
                        continue
                
                if not object_types:
                    continue
                
                # Execute batch SNMP GET with timing
                batch_start = __import__('time').time()
                error_indication, error_status, error_index, var_binds = await getCmd(
                    self.engine, self.auth_data, self.transport_target, self.context_data, *object_types
                )
                batch_elapsed = __import__('time').time() - batch_start
                _LOGGER.debug("Value batch %d/%d completed in %.2fs", batch_num, total_batches, batch_elapsed)
                
                if error_indication:
                    _LOGGER.debug("SNMP batch error indication: %s", error_indication)
                    continue
                    
                if error_status:
                    _LOGGER.debug("SNMP batch error status: %s at index %s", error_status, error_index)
                    continue
                
                # Process results
                for name, val in var_binds:
                    oid_str = str(name)
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        try:
                            results[oid_str] = int(val)
                        except (ValueError, TypeError):
                            pass  # Skip non-numeric values
                            
            except Exception as exc:
                _LOGGER.debug("Failed to get SNMP batch values: %s", exc)
                
        return results
    
    async def _bulk_get_strings(self, oids: list[str]) -> dict[str, str]:
        """Get multiple SNMP values as strings using bulk operations."""
        # Don't call _ensure_initialized again if already called
        if self.context_data is None:
            _LOGGER.error("SNMP context_data is None - initialization was not successful")
            return {}
        
        if not oids:
            return {}
            
        results = {}
        
        # Process OIDs in batches of 25 for better performance
        batch_size = 25
        total_batches = (len(oids) + batch_size - 1) // batch_size
        _LOGGER.debug("Processing %d string OIDs in %d batches of %d", len(oids), total_batches, batch_size)
        
        for batch_num, i in enumerate(range(0, len(oids), batch_size), 1):
            batch_oids = oids[i:i + batch_size]
            _LOGGER.debug("Processing string batch %d/%d with %d OIDs", batch_num, total_batches, len(batch_oids))
            
            try:
                # Create ObjectType list for batch
                object_types = []
                for oid in batch_oids:
                    try:
                        object_types.append(ObjectType(ObjectIdentity(oid)))
                    except Exception as oid_exc:
                        _LOGGER.debug("Failed to create ObjectType for OID %s: %s", oid, oid_exc)
                        continue
                
                if not object_types:
                    continue
                
                # Execute batch SNMP GET with timing
                batch_start = __import__('time').time()
                error_indication, error_status, error_index, var_binds = await getCmd(
                    self.engine, self.auth_data, self.transport_target, self.context_data, *object_types
                )
                batch_elapsed = __import__('time').time() - batch_start
                _LOGGER.debug("String batch %d/%d completed in %.2fs", batch_num, total_batches, batch_elapsed)
                
                if error_indication:
                    _LOGGER.debug("SNMP batch error indication: %s", error_indication)
                    continue
                    
                if error_status:
                    _LOGGER.debug("SNMP batch error status: %s at index %s", error_status, error_index)
                    continue
                
                # Process results
                for name, val in var_binds:
                    oid_str = str(name)
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        try:
                            string_val = str(val).strip()
                            if string_val:  # Only add non-empty strings
                                results[oid_str] = string_val
                        except Exception as val_exc:
                            _LOGGER.debug("Failed to convert SNMP value to string for OID %s: %s", oid_str, val_exc)
                            
            except Exception as exc:
                _LOGGER.debug("Failed to get SNMP batch strings: %s", exc)
                
        return results