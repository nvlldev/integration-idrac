"""SNMP data processor for Dell iDRAC integration.

This module handles the processing of raw SNMP data into structured sensor information.
It contains all the logic for interpreting SNMP values, applying unit conversions,
checking status codes, and organizing data into sensor categories.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from ..const import (
    IDRAC_OIDS,
    PSU_STATUS,
    FAN_STATUS,
    TEMP_STATUS,
    MEMORY_HEALTH_STATUS,
    INTRUSION_STATUS,
    BATTERY_STATUS,
    PROCESSOR_STATUS,
)
from ..utils import format_oid_with_index

_LOGGER = logging.getLogger(__name__)


class SNMPDataProcessor:
    """Processes raw SNMP data into structured sensor information.
    
    This class handles the conversion of SNMP OID values and strings into
    properly formatted sensor data dictionaries. It includes logic for:
    - Temperature unit conversion and threshold processing
    - Fan speed and status interpretation
    - PSU power calculations and status mapping
    - Memory module information processing
    - Voltage probe data formatting
    - Status code mapping for all sensor types
    """
    
    def __init__(self, discovered_sensors: Dict[str, list]):
        """Initialize the processor with discovered sensor indices.
        
        Args:
            discovered_sensors: Dictionary containing lists of discovered sensor
                               indices for each sensor type (cpus, fans, psus, etc.)
        """
        self.discovered_cpus = discovered_sensors.get('cpus', [])
        self.discovered_temperatures = discovered_sensors.get('temperatures', [])
        self.discovered_fans = discovered_sensors.get('fans', [])
        self.discovered_psus = discovered_sensors.get('psus', [])
        self.discovered_voltage_probes = discovered_sensors.get('voltage_probes', [])
        self.discovered_memory = discovered_sensors.get('memory', [])
        self.discovered_virtual_disks = discovered_sensors.get('virtual_disks', [])
        self.discovered_physical_disks = discovered_sensors.get('physical_disks', [])
        self.discovered_storage_controllers = discovered_sensors.get('storage_controllers', [])
        self.discovered_detailed_memory = discovered_sensors.get('detailed_memory', [])
        self.discovered_system_voltages = discovered_sensors.get('system_voltages', [])
        self.discovered_power_consumption = discovered_sensors.get('power_consumption', [])
        self.discovered_intrusion = discovered_sensors.get('intrusion', [])
        self.discovered_battery = discovered_sensors.get('battery', [])
        self.discovered_processors = discovered_sensors.get('processors', [])
        
    def process_snmp_data(self, values: Dict[str, int], strings: Dict[str, str]) -> Dict[str, Any]:
        """Process raw SNMP data into organized sensor information.
        
        Args:
            values: Dictionary of OID -> integer value mappings from SNMP
            strings: Dictionary of OID -> string value mappings from SNMP
            
        Returns:
            Dictionary containing organized sensor data by category
        """
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
            "system_info": {},
        }
        
        # Sanitize data types before processing
        values = self._sanitize_values_dict(values)
        
        # Process each sensor category with error handling
        try:
            self._process_temperature_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing temperature sensors: %s", exc)
            
        try:
            self._process_fan_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing fan sensors: %s", exc)
            
        try:
            self._process_psu_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing PSU sensors: %s", exc)
            
        try:
            self._process_memory_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing memory sensors: %s", exc)
            
        try:
            self._process_voltage_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing voltage sensors: %s", exc)
            
        try:
            self._process_power_consumption(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing power consumption: %s", exc)
            
        try:
            self._process_intrusion_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing intrusion sensors: %s", exc)
            
        try:
            self._process_battery_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing battery sensors: %s", exc)
            
        try:
            self._process_processor_sensors(data, values, strings)
        except Exception as exc:
            _LOGGER.warning("Error processing processor sensors: %s", exc)
        
        return data
    
    def _sanitize_values_dict(self, values: Dict[str, Any]) -> Dict[str, int]:
        """Sanitize the values dictionary to ensure all values are integers.
        
        Args:
            values: Raw values dictionary that may contain mixed data types
            
        Returns:
            Dictionary with only valid integer values
        """
        sanitized = {}
        
        for oid, value in values.items():
            if value is None:
                continue
                
            try:
                # Try to convert to integer
                if isinstance(value, str):
                    # Handle string representations of integers
                    if value.strip():  # Only process non-empty strings
                        sanitized[oid] = int(value)
                elif isinstance(value, (int, float)):
                    sanitized[oid] = int(value)
                else:
                    _LOGGER.debug("Skipping non-numeric SNMP value for OID %s: %s (type: %s)", 
                                oid, repr(value), type(value).__name__)
            except (ValueError, TypeError) as exc:
                _LOGGER.debug("Failed to convert SNMP value to int for OID %s (value: %s): %s", 
                            oid, repr(value), exc)
                
        return sanitized
    
    def _process_temperature_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process temperature sensor data from SNMP values."""
        processed_count = 0
        
        # Process CPU temperature sensors (legacy)
        for cpu_id in self.discovered_cpus:
            temp_oid = format_oid_with_index(IDRAC_OIDS["temp_probe_reading"], cpu_id)
            temp_reading = values.get(temp_oid)
            
            if temp_reading is not None:
                # Convert temperature value (Dell reports in tenths of degrees Celsius)
                temperature_celsius = self._convert_temperature(temp_reading)
                
                # Get additional temperature data
                temp_status = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_status"], cpu_id))
                temp_location = strings.get(format_oid_with_index(IDRAC_OIDS["temp_probe_location"], cpu_id))
                temp_upper_critical = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_upper_critical"], cpu_id))
                temp_upper_warning = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_upper_warning"], cpu_id))
                
                sensor_data = {
                    "name": temp_location or f"CPU {cpu_id} Temperature",
                    "temperature": temperature_celsius,
                    "status": TEMP_STATUS.get(temp_status, "unknown"),
                    "upper_threshold_critical": self._convert_temperature(temp_upper_critical) if temp_upper_critical else None,
                    "upper_threshold_non_critical": self._convert_temperature(temp_upper_warning) if temp_upper_warning else None,
                }
                
                data["temperatures"][f"cpu_temp_{cpu_id}"] = sensor_data
                processed_count += 1
                
                # Log temperature anomalies
                self._check_temperature_anomalies(sensor_data, cpu_id)
            else:
                _LOGGER.debug("No temperature reading for discovered CPU sensor %d", cpu_id)
        
        # Process ALL temperature sensors (including inlet, outlet, system, etc.)
        for temp_id in self.discovered_temperatures:
            # Skip if already processed as CPU sensor
            if temp_id in self.discovered_cpus:
                continue
                
            temp_oid = format_oid_with_index(IDRAC_OIDS["temp_probe_reading"], temp_id)
            temp_reading = values.get(temp_oid)
            
            if temp_reading is not None:
                # Convert temperature value (Dell reports in tenths of degrees Celsius)
                temperature_celsius = self._convert_temperature(temp_reading)
                
                # Get additional temperature data
                temp_status = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_status"], temp_id))
                temp_location = strings.get(format_oid_with_index(IDRAC_OIDS["temp_probe_location"], temp_id))
                temp_upper_critical = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_upper_critical"], temp_id))
                temp_upper_warning = values.get(format_oid_with_index(IDRAC_OIDS["temp_probe_upper_warning"], temp_id))
                
                sensor_data = {
                    "name": temp_location or f"Temperature {temp_id}",
                    "temperature": temperature_celsius,
                    "status": TEMP_STATUS.get(temp_status, "unknown"),
                    "upper_threshold_critical": self._convert_temperature(temp_upper_critical) if temp_upper_critical else None,
                    "upper_threshold_non_critical": self._convert_temperature(temp_upper_warning) if temp_upper_warning else None,
                }
                
                data["temperatures"][f"temp_{temp_id}"] = sensor_data
                processed_count += 1
                
                # Log temperature anomalies for non-CPU sensors too
                self._check_temperature_anomalies(sensor_data, temp_id)
                
                # Debug log for inlet/outlet detection
                location_lower = temp_location.lower() if temp_location else ""
                if any(pattern in location_lower for pattern in ["inlet", "intake", "ambient", "outlet", "exhaust", "exit"]):
                    _LOGGER.info("Found airflow temperature sensor: %s (ID: %d)", temp_location, temp_id)
            else:
                _LOGGER.debug("No temperature reading for discovered temperature sensor %d", temp_id)
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d temperature sensors", processed_count)
    
    def _process_fan_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process fan sensor data from SNMP values."""
        processed_count = 0
        
        for fan_id in self.discovered_fans:
            fan_reading = values.get(format_oid_with_index(IDRAC_OIDS["cooling_device_reading"], fan_id))
            
            if fan_reading is not None:
                fan_status = values.get(format_oid_with_index(IDRAC_OIDS["cooling_device_status"], fan_id))
                fan_location = strings.get(format_oid_with_index(IDRAC_OIDS["cooling_device_location"], fan_id))
                
                sensor_data = {
                    "name": fan_location or f"Fan {fan_id}",
                    "speed_rpm": fan_reading,
                    "status": FAN_STATUS.get(fan_status, "unknown"),
                }
                
                data["fans"][f"fan_{fan_id}"] = sensor_data
                processed_count += 1
                
                # Log fan anomalies
                self._check_fan_anomalies(sensor_data, fan_id)
            else:
                _LOGGER.debug("No fan reading for discovered cooling sensor %d", fan_id)
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d fan sensors", processed_count)
    
    def _process_psu_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process PSU sensor data from SNMP values."""
        processed_count = 0
        
        for psu_id in self.discovered_psus:
            psu_status = values.get(format_oid_with_index(IDRAC_OIDS["psu_status"], psu_id))
            psu_location = strings.get(format_oid_with_index(IDRAC_OIDS["psu_location"], psu_id))
            
            if psu_status is not None and psu_location:
                psu_max_output = values.get(format_oid_with_index(IDRAC_OIDS["psu_max_output"], psu_id))
                psu_current_output = values.get(format_oid_with_index(IDRAC_OIDS["psu_current_output"], psu_id))
                
                sensor_data = {
                    "name": psu_location,
                    "status": PSU_STATUS.get(psu_status, "unknown"),
                    "power_capacity_watts": psu_max_output,
                    "power_output_watts": psu_current_output,
                }
                
                data["power_supplies"][f"psu_{psu_id}"] = sensor_data
                processed_count += 1
                
                # Log PSU anomalies
                self._check_psu_anomalies(sensor_data, psu_id)
            else:
                _LOGGER.debug("Incomplete PSU data for sensor %d (status: %s, location: %s)", 
                             psu_id, psu_status, psu_location)
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d PSU sensors", processed_count)
    
    def _process_memory_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process memory sensor data from SNMP values."""
        processed_count = 0
        
        for memory_id in self.discovered_memory:
            memory_status = values.get(format_oid_with_index(IDRAC_OIDS["memory_status"], memory_id))
            memory_location = strings.get(format_oid_with_index(IDRAC_OIDS["memory_location"], memory_id))
            
            if memory_status is not None and memory_location:
                memory_size = values.get(format_oid_with_index(IDRAC_OIDS["memory_size"], memory_id))
                
                sensor_data = {
                    "name": memory_location,
                    "status": MEMORY_HEALTH_STATUS.get(memory_status, "unknown"),
                    "size_kb": memory_size,
                }
                
                data["memory"][f"memory_{memory_id}"] = sensor_data
                processed_count += 1
                
                # Log memory anomalies
                self._check_memory_anomalies(sensor_data, memory_id)
            else:
                _LOGGER.debug("Incomplete memory data for sensor %d", memory_id)
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d memory sensors", processed_count)
            
            # Calculate total system memory from individual memory modules
            total_memory_kb = 0
            for memory_data in data["memory"].values():
                if isinstance(memory_data, dict) and "size_kb" in memory_data:
                    size_kb = memory_data["size_kb"]
                    if size_kb is not None:
                        try:
                            total_memory_kb += int(size_kb)
                        except (ValueError, TypeError):
                            _LOGGER.debug("Invalid memory size value: %s", size_kb)
            
            # Convert KB to GB and store in system_info for compatibility with Redfish
            if total_memory_kb > 0:
                total_memory_gb = round(total_memory_kb / (1024 * 1024), 2)  # KB to GB
                data["system_info"]["memory_gb"] = total_memory_gb
                _LOGGER.debug("Calculated total system memory: %.2f GB from %d modules", 
                             total_memory_gb, processed_count)
    
    def _process_voltage_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process voltage sensor data from SNMP values."""
        processed_count = 0
        skipped_count = 0
        
        for voltage_id in self.discovered_voltage_probes:
            voltage_reading = values.get(format_oid_with_index(IDRAC_OIDS["psu_input_voltage"], voltage_id))
            
            if voltage_reading is not None:
                voltage_location = strings.get(format_oid_with_index(IDRAC_OIDS["psu_location"], voltage_id))
                
                # Debug log all voltage sensors for troubleshooting
                _LOGGER.debug("Found voltage sensor ID %d: location='%s'", voltage_id, voltage_location or "No location")
                
                # Improve PSU voltage sensor names for clarity
                improved_name = voltage_location
                if voltage_location:
                    location_lower = voltage_location.lower()
                    # Handle specific patterns to get clean names
                    if "ps1 voltage" in location_lower:
                        improved_name = "Power Supply 1"
                    elif "ps2 voltage" in location_lower:
                        improved_name = "Power Supply 2"
                    elif "ps3 voltage" in location_lower:
                        improved_name = "Power Supply 3"
                    elif "ps1" in location_lower:
                        improved_name = voltage_location.replace("PS1", "Power Supply 1").replace("ps1", "Power Supply 1")
                    elif "ps2" in location_lower:
                        improved_name = voltage_location.replace("PS2", "Power Supply 2").replace("ps2", "Power Supply 2")
                    elif "ps3" in location_lower:
                        improved_name = voltage_location.replace("PS3", "Power Supply 3").replace("ps3", "Power Supply 3")
                    elif "psu" in location_lower and "voltage" in location_lower:
                        # Extract PSU number and create clean name
                        psu_match = re.search(r'psu\s*(\d+)', location_lower)
                        if psu_match:
                            psu_num = psu_match.group(1)
                            improved_name = f"Power Supply {psu_num}"
                
                # Skip power consumption sensors that show up as voltage sensors
                # This must be checked BEFORE system board binary sensor logic
                if voltage_location and any(power_term in voltage_location.lower() for power_term in ["pwr consumption", "power consumption", "consumption", "board pwr consumption"]):
                    _LOGGER.debug("Skipping power consumption voltage sensor: %s", voltage_location)
                    skipped_count += 1
                    continue
                
                # Skip voltage sensors without meaningful location names (likely unwanted system voltages)
                if not voltage_location or voltage_location.strip() == "":
                    _LOGGER.debug("Skipping voltage sensor %d: no location name", voltage_id)
                    skipped_count += 1
                    continue
                
                # Handle voltage status indicators as binary sensors (they're status indicators, not real voltages)
                # This includes System Board voltages and CPU PG (Power Good) signals
                location_lower = voltage_location.lower() if voltage_location else ""
                is_status_indicator = (
                    "system board" in location_lower or
                    " pg" in location_lower or
                    location_lower.endswith(" pg") or
                    "power good" in location_lower
                )
                
                if is_status_indicator:
                    # Convert voltage reading (typically in millivolts)  
                    voltage_volts = self._convert_voltage(voltage_reading)
                    
                    # Voltage status indicators are binary signals (1V = OK, 0V = Not OK)
                    is_ok = voltage_volts > 0.5  # Consider > 0.5V as "OK"
                    
                    # Clean up the sensor name
                    clean_name = voltage_location.replace(" Voltage", "").replace(" PG", " Power Good")
                    
                    # Format CPU PG sensors properly: "CPU1 PG" -> "CPU 1 Power Good"
                    cpu_match = re.match(r'^CPU(\d+)', clean_name)
                    if cpu_match:
                        cpu_num = cpu_match.group(1)
                        clean_name = re.sub(r'^CPU\d+', f'CPU {cpu_num}', clean_name)
                    
                    sensor_data = {
                        "name": clean_name,
                        "reading": 1 if is_ok else 0,  # Binary reading for binary sensor
                        "status": "ok" if is_ok else "critical",
                        "voltage_value": voltage_volts,  # Keep original voltage for debugging
                        "sensor_type": "power_good" if " pg" in location_lower else "system_voltage",
                    }
                    
                    # Store in system_voltages for binary sensor processing
                    if "system_voltages" not in data:
                        data["system_voltages"] = {}
                    data["system_voltages"][f"system_voltage_{voltage_id}"] = sensor_data
                    _LOGGER.debug("Added voltage status indicator as binary sensor: %s -> %s", voltage_location, clean_name)
                    processed_count += 1
                    continue
                
                # Regular voltage sensors (PSU input voltages, etc.)
                # Convert voltage reading (typically in millivolts)
                voltage_volts = self._convert_voltage(voltage_reading)
                
                sensor_data = {
                    "name": f"{improved_name} Input Voltage" if improved_name else f"Voltage {voltage_id}",
                    "reading_volts": voltage_volts,
                    "status": "ok",  # Voltage probes typically don't have explicit status
                }
                
                data["voltages"][f"voltage_{voltage_id}"] = sensor_data
                processed_count += 1
            else:
                _LOGGER.debug("No voltage reading for sensor %d", voltage_id)
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d voltage sensors", processed_count)
        if skipped_count > 0:
            _LOGGER.debug("Skipped %d PSU voltage sensors per user request", skipped_count)
    
    def _process_power_consumption(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process system power consumption data."""
        if self.discovered_power_consumption:
            power_current = values.get(IDRAC_OIDS["power_consumption_current"])
            if power_current is not None:
                power_peak = values.get(IDRAC_OIDS["power_consumption_peak"])
                data["power_consumption"] = {
                    "consumed_watts": power_current,
                    "max_consumed_watts": power_peak,
                }
                _LOGGER.debug("Processed power consumption data")
    
    def _process_intrusion_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process chassis intrusion sensor data."""
        processed_count = 0
        
        _LOGGER.debug("Processing intrusion sensors. Discovered IDs: %s", self.discovered_intrusion)
        
        for intrusion_id in self.discovered_intrusion:
            intrusion_reading = values.get(format_oid_with_index(IDRAC_OIDS["intrusion_reading"], intrusion_id))
            intrusion_status = values.get(format_oid_with_index(IDRAC_OIDS["intrusion_status"], intrusion_id))
            intrusion_location = strings.get(format_oid_with_index(IDRAC_OIDS["intrusion_location"], intrusion_id))
            
            _LOGGER.debug("Intrusion sensor %s: reading=%s, status=%s, location=%s", 
                         intrusion_id, intrusion_reading, intrusion_status, intrusion_location)
            
            if intrusion_reading is not None and intrusion_location:
                sensor_data = {
                    "name": intrusion_location,
                    "reading": intrusion_reading,
                    "status": intrusion_status,  # Store raw numeric status for binary sensor
                    "status_text": INTRUSION_STATUS.get(intrusion_status, "unknown"),  # Keep text version for reference
                }
                
                data["intrusion_detection"][f"intrusion_{intrusion_id}"] = sensor_data
                processed_count += 1
                
                # Log intrusion events
                if intrusion_status and intrusion_status != 3:  # 3 = ok
                    _LOGGER.warning("Intrusion detected: %s (status: %s)", 
                                  intrusion_location, INTRUSION_STATUS.get(intrusion_status, intrusion_status))
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d intrusion sensors", processed_count)
    
    def _process_battery_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process system battery sensor data."""
        processed_count = 0
        
        for battery_id in self.discovered_battery:
            battery_reading = values.get(format_oid_with_index(IDRAC_OIDS["battery_reading"], battery_id))
            battery_status = values.get(format_oid_with_index(IDRAC_OIDS["battery_status"], battery_id))
            
            if battery_reading is not None and battery_status is not None:
                sensor_data = {
                    "name": f"System Battery {battery_id}",
                    "reading": battery_reading,
                    "status": BATTERY_STATUS.get(battery_status, "unknown"),
                }
                
                data["battery"][f"battery_{battery_id}"] = sensor_data
                processed_count += 1
                
                # Log battery issues
                if battery_status and battery_status != 3:  # 3 = ok
                    _LOGGER.warning("Battery issue detected: Battery %d (status: %s)", 
                                  battery_id, BATTERY_STATUS.get(battery_status, battery_status))
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d battery sensors", processed_count)
    
    def _process_processor_sensors(self, data: Dict[str, Any], values: Dict[str, int], strings: Dict[str, str]) -> None:
        """Process processor sensor data."""
        processed_count = 0
        
        for processor_id in self.discovered_processors:
            processor_reading = values.get(format_oid_with_index(IDRAC_OIDS["processor_reading"], processor_id))
            processor_status = values.get(format_oid_with_index(IDRAC_OIDS["processor_status"], processor_id))
            processor_location = strings.get(format_oid_with_index(IDRAC_OIDS["processor_location"], processor_id))
            
            if processor_reading is not None and processor_location:
                sensor_data = {
                    "name": processor_location,
                    "reading": processor_reading,
                    "status": PROCESSOR_STATUS.get(processor_status, "unknown"),
                }
                
                data["processors"][f"processor_{processor_id}"] = sensor_data
                processed_count += 1
                
                # Log processor issues
                if processor_status and processor_status != 3:  # 3 = ok
                    _LOGGER.warning("Processor issue detected: %s (status: %s)", 
                                  processor_location, PROCESSOR_STATUS.get(processor_status, processor_status))
        
        if processed_count > 0:
            _LOGGER.debug("Processed %d processor sensors", processed_count)
    
    # Utility methods for data conversion and anomaly detection
    
    def _convert_temperature(self, raw_value: int | None) -> float | None:
        """Convert raw temperature value to Celsius.
        
        Dell iDRAC typically reports temperatures in tenths of degrees Celsius.
        Values > 100 are assumed to be in tenths (e.g., 580 = 58.0°C).
        Values <= 100 are assumed to be direct Celsius values.
        """
        if raw_value is None:
            return None
        
        try:
            # Handle string values that might have been passed incorrectly
            if isinstance(raw_value, str):
                raw_value = int(raw_value)
            elif not isinstance(raw_value, (int, float)):
                _LOGGER.warning("Invalid temperature value type: %s (value: %s)", type(raw_value).__name__, repr(raw_value))
                return None
                
            return raw_value / 10.0 if raw_value > 100 else float(raw_value)
        except (ValueError, TypeError) as exc:
            _LOGGER.warning("Failed to convert temperature value %s: %s", repr(raw_value), exc)
            return None
    
    def _convert_voltage(self, raw_value: int) -> float | None:
        """Convert raw voltage value to volts.
        
        Dell iDRAC typically reports voltages in millivolts.
        Values > 1000 are assumed to be in millivolts and converted to volts.
        """
        if raw_value is None:
            return None
            
        try:
            # Handle string values that might have been passed incorrectly
            if isinstance(raw_value, str):
                raw_value = int(raw_value)
            elif not isinstance(raw_value, (int, float)):
                _LOGGER.warning("Invalid voltage value type: %s (value: %s)", type(raw_value).__name__, repr(raw_value))
                return None
                
            return raw_value / 1000.0 if raw_value > 1000 else float(raw_value)
        except (ValueError, TypeError) as exc:
            _LOGGER.warning("Failed to convert voltage value %s: %s", repr(raw_value), exc)
            return None
    
    def _check_temperature_anomalies(self, sensor_data: Dict[str, Any], sensor_id: int) -> None:
        """Check for temperature anomalies and log warnings."""
        temp = sensor_data.get("temperature")
        status = sensor_data.get("status")
        name = sensor_data.get("name", f"CPU {sensor_id}")
        
        if temp and temp > 80:
            _LOGGER.warning("High temperature detected: %s = %.1f°C", name, temp)
        elif status and status not in ["ok", "unknown"]:
            _LOGGER.warning("Temperature sensor status issue: %s status = %s", name, status)
    
    def _check_fan_anomalies(self, sensor_data: Dict[str, Any], sensor_id: int) -> None:
        """Check for fan anomalies and log warnings."""
        speed = sensor_data.get("speed_rpm")
        status = sensor_data.get("status")
        name = sensor_data.get("name", f"Fan {sensor_id}")
        
        if speed and speed < 500:
            _LOGGER.warning("Low fan speed detected: %s = %d RPM", name, speed)
        elif status and status not in ["ok", "unknown"]:
            _LOGGER.warning("Fan status issue: %s status = %s", name, status)
    
    def _check_psu_anomalies(self, sensor_data: Dict[str, Any], sensor_id: int) -> None:
        """Check for PSU anomalies and log warnings."""
        status = sensor_data.get("status")
        name = sensor_data.get("name", f"PSU {sensor_id}")
        
        if status and status not in ["ok", "unknown"]:
            _LOGGER.warning("PSU status issue: %s status = %s", name, status)
    
    def _check_memory_anomalies(self, sensor_data: Dict[str, Any], sensor_id: int) -> None:
        """Check for memory anomalies and log warnings."""
        status = sensor_data.get("status")
        name = sensor_data.get("name", f"Memory {sensor_id}")
        
        if status and status not in ["ok", "unknown"]:
            _LOGGER.warning("Memory status issue: %s status = %s", name, status)