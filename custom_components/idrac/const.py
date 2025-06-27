"""Constants for the Dell iDRAC integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "idrac"

# Configuration constants
CONF_COMMUNITY: Final = "community"
CONF_SNMP_VERSION: Final = "snmp_version"
CONF_USERNAME: Final = "username"
CONF_AUTH_PROTOCOL: Final = "auth_protocol"
CONF_AUTH_PASSWORD: Final = "auth_password"
CONF_PRIV_PROTOCOL: Final = "priv_protocol"
CONF_PRIV_PASSWORD: Final = "priv_password"
CONF_PORT: Final = "port"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_DISCOVERED_FANS: Final = "discovered_fans"
CONF_DISCOVERED_CPUS: Final = "discovered_cpus"
CONF_DISCOVERED_PSUS: Final = "discovered_psus"
CONF_DISCOVERED_VOLTAGE_PROBES: Final = "discovered_voltage_probes"
CONF_DISCOVERED_MEMORY: Final = "discovered_memory"
CONF_DISCOVERED_VIRTUAL_DISKS: Final = "discovered_virtual_disks"
CONF_DISCOVERED_PHYSICAL_DISKS: Final = "discovered_physical_disks"
CONF_DISCOVERED_STORAGE_CONTROLLERS: Final = "discovered_storage_controllers"
CONF_DISCOVERED_DETAILED_MEMORY: Final = "discovered_detailed_memory"
CONF_DISCOVERED_SYSTEM_VOLTAGES: Final = "discovered_system_voltages"
CONF_DISCOVERED_POWER_CONSUMPTION: Final = "discovered_power_consumption"
CONF_DISCOVERED_INTRUSION: Final = "discovered_intrusion"
CONF_DISCOVERED_BATTERY: Final = "discovered_battery"
CONF_DISCOVERED_PROCESSORS: Final = "discovered_processors"
CONF_REQUEST_TIMEOUT: Final = "request_timeout"
CONF_SESSION_TIMEOUT: Final = "session_timeout"
CONF_SNMP_PORT: Final = "snmp_port"

# Default values
DEFAULT_PORT: Final = 443
DEFAULT_SNMP_PORT: Final = 161
DEFAULT_COMMUNITY: Final = "public"
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_SNMP_VERSION: Final = "v2c"
DEFAULT_CONNECTION_TYPE: Final = "redfish"
DEFAULT_REQUEST_TIMEOUT: Final = 60
DEFAULT_SESSION_TIMEOUT: Final = 90

# Connection type options
CONNECTION_TYPES: Final = ["redfish", "snmp", "hybrid"]

# SNMP version options
SNMP_VERSIONS: Final = ["v2c", "v3"]

# SNMP v3 authentication protocols
SNMP_AUTH_PROTOCOLS: Final[dict[str, str]] = {
    "none": "usmNoAuthProtocol",
    "md5": "usmHMACMD5AuthProtocol", 
    "sha": "usmHMACSHAAuthProtocol",
    "sha224": "usmHMAC128SHA224AuthProtocol",
    "sha256": "usmHMAC192SHA256AuthProtocol",
    "sha384": "usmHMAC256SHA384AuthProtocol",
    "sha512": "usmHMAC384SHA512AuthProtocol"
}

# SNMP v3 privacy protocols  
SNMP_PRIV_PROTOCOLS: Final[dict[str, str]] = {
    "none": "usmNoPrivProtocol",
    "des": "usmDESPrivProtocol",
    "3des": "usm3DESEDEPrivProtocol", 
    "aes128": "usmAesCfb128Protocol",
    "aes192": "usmAesCfb192Protocol",
    "aes256": "usmAesCfb256Protocol"
}

# Redfish status mappings for Health values
REDFISH_HEALTH_STATUS: Final[dict[str | None, str]] = {
    "OK": "ok",
    "Warning": "warning", 
    "Critical": "critical",
    None: "unknown"
}

# Redfish state mappings for State values
REDFISH_STATE_STATUS: Final[dict[str | None, str]] = {
    "Enabled": "enabled",
    "Disabled": "disabled",
    "StandbyOffline": "standby",
    "StandbySpare": "standby_spare",
    "InTest": "testing",
    "Starting": "starting",
    "Absent": "absent",
    "UnavailableOffline": "offline",
    None: "unknown"
}

# Power state mappings
POWER_STATE_STATUS: Final[dict[str | None, str]] = {
    "On": "on",
    "Off": "off",
    "PoweringOn": "powering_on",
    "PoweringOff": "powering_off",
    None: "unknown"
}

# Dell iDRAC SNMP OIDs - Updated with verified working OIDs from comprehensive discovery
IDRAC_OIDS: Final = {
    # System Information
    "system_manufacturer": "1.3.6.1.2.1.1.5.0",  # SNMPv2-MIB::sysName
    "system_model": "1.3.6.1.4.1.674.10892.5.1.3.12.0",  # Dell system model
    "system_service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",  # Dell service tag
    "system_bios_version": "1.3.6.1.4.1.674.10892.5.1.3.6.0",  # Dell BIOS version
    
    # Thermal sensors
    "temp_probe_location": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.{index}",
    "temp_probe_reading": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.{index}",
    "temp_probe_status": "1.3.6.1.4.1.674.10892.5.4.700.20.1.5.1.{index}",
    "temp_probe_upper_critical": "1.3.6.1.4.1.674.10892.5.4.700.20.1.10.1.{index}",
    "temp_probe_upper_warning": "1.3.6.1.4.1.674.10892.5.4.700.20.1.11.1.{index}",
    
    # Cooling devices (fans)
    "cooling_device_location": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.{index}",
    "cooling_device_reading": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.{index}",
    "cooling_device_status": "1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1.{index}",
    "cooling_device_warn_upper": "1.3.6.1.4.1.674.10892.5.4.700.12.1.10.1.{index}",
    
    # Power Supply status and information
    "psu_location": "1.3.6.1.4.1.674.10892.5.4.600.12.1.8.1.{index}",
    "psu_status": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1.{index}",
    "psu_input_voltage": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.{index}",
    "psu_max_output": "1.3.6.1.4.1.674.10892.5.4.600.12.1.15.1.{index}",
    "psu_current_output": "1.3.6.1.4.1.674.10892.5.4.600.12.1.16.1.{index}",
    
    # Power consumption  
    "power_consumption_current": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
    "power_consumption_peak": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3",
    
    # Memory modules
    "memory_location": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1.{index}",
    "memory_status": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1.{index}",
    "memory_size": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1.{index}",
    "memory_type": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7.1.{index}",
    "memory_speed": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.15.1.{index}",
    
    # Virtual Disks
    "virtual_disk_name": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2.1.{index}",
    "virtual_disk_status": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4.1.{index}",
    "virtual_disk_size": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.6.1.{index}",
    "virtual_disk_raid_level": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.7.1.{index}",
    
    # Physical Disks
    "physical_disk_name": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.2.1.{index}",
    "physical_disk_status": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.4.1.{index}",
    "physical_disk_size": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.11.1.{index}",
    "physical_disk_media_type": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.35.1.{index}",
    
    # Storage Controllers
    "storage_controller_name": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.2.1.{index}",
    "storage_controller_status": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.38.1.{index}",
    "storage_controller_firmware": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.8.1.{index}",
    
    # System Voltages
    "system_voltage_location": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.{index}",
    "system_voltage_reading": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1.{index}",
    "system_voltage_status": "1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1.{index}",
    "system_voltage_upper_critical": "1.3.6.1.4.1.674.10892.5.4.600.20.1.10.1.{index}",
    "system_voltage_lower_critical": "1.3.6.1.4.1.674.10892.5.4.600.20.1.11.1.{index}",
    
    # System control buttons
    "power_button": "1.3.6.1.4.1.674.10892.5.4.200.10.1.11.1.1",  # Power button action
    "reset_button": "1.3.6.1.4.1.674.10892.5.4.200.10.1.11.1.2",  # Reset button action
    
    # Chassis intrusion detection (SNMP available!)
    "intrusion_location": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1.{index}",
    "intrusion_reading": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.{index}",
    "intrusion_status": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.{index}",
    
    # System battery
    "battery_reading": "1.3.6.1.4.1.674.10892.5.4.600.50.1.6.1.{index}",
    "battery_status": "1.3.6.1.4.1.674.10892.5.4.600.50.1.5.1.{index}",
    
    # Processor sensors
    "processor_location": "1.3.6.1.4.1.674.10892.5.4.1200.10.1.8.1.{index}",
    "processor_reading": "1.3.6.1.4.1.674.10892.5.4.1200.10.1.6.1.{index}",
    "processor_status": "1.3.6.1.4.1.674.10892.5.4.1200.10.1.5.1.{index}",
}

# SNMP Walk OIDs for discovery
SNMP_WALK_OIDS: Final = {
    "fans": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1",
    "cpu_temps": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1",
    "psu_status": "1.3.6.1.4.1.674.10892.5.4.600.12.1.8.1",
    "psu_voltage": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1",
    "memory": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1",
    "virtual_disks": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2.1",
    "physical_disks": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.2.1",
    "storage_controllers": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.2.1",
    "detailed_memory": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1",
    "system_voltages": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1",
    "power_consumption": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    "intrusion_detection": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1",
    "system_battery": "1.3.6.1.4.1.674.10892.5.4.600.50.1.6.1",
    "processors": "1.3.6.1.4.1.674.10892.5.4.1200.10.1.8.1",
}

# Status mappings for SNMP values
PSU_STATUS: Final = {
    1: "other",
    2: "unknown", 
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

FAN_STATUS: Final = {
    1: "other",
    2: "unknown",
    3: "ok", 
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

TEMP_STATUS: Final = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical_upper",
    5: "critical_upper", 
    6: "non_recoverable_upper",
    7: "non_critical_lower",
    8: "critical_lower",
    9: "non_recoverable_lower",
    10: "failed"
}

MEMORY_HEALTH_STATUS: Final = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

STORAGE_HEALTH_STATUS: Final = {
    1: "other",
    2: "unknown", 
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

INTRUSION_STATUS: Final = {
    1: "breach",
    2: "no_breach", 
    3: "ok",
    4: "unknown"
}

BATTERY_STATUS: Final = {
    1: "other",
    2: "unknown",
    3: "ok", 
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

PROCESSOR_STATUS: Final = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical", 
    5: "critical",
    6: "non_recoverable"
}