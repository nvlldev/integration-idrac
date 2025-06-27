"""Constants for the Dell iDRAC integration."""
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
CONF_DISCOVERED_FANS: Final = "discovered_fans"
CONF_DISCOVERED_CPUS: Final = "discovered_cpus"
CONF_DISCOVERED_PSUS: Final = "discovered_psus"
CONF_DISCOVERED_VOLTAGE_PROBES: Final = "discovered_voltage_probes"
CONF_DISCOVERED_MEMORY: Final = "discovered_memory"
CONF_DISCOVERED_VIRTUAL_DISKS: Final = "discovered_virtual_disks"
CONF_DISCOVERED_PHYSICAL_DISKS: Final = "discovered_physical_disks"
CONF_DISCOVERED_STORAGE_CONTROLLERS: Final = "discovered_storage_controllers"
CONF_DISCOVERED_DETAILED_MEMORY: Final = "discovered_detailed_memory"
CONF_DISCOVERED_POWER_CONSUMPTION: Final = "discovered_power_consumption"
CONF_DISCOVERED_SYSTEM_VOLTAGES: Final = "discovered_system_voltages"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_PORT: Final = 161
DEFAULT_COMMUNITY: Final = "public"
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_SNMP_VERSION: Final = "v2c"

# SNMP version options
SNMP_VERSIONS: Final = ["v2c", "v3"]

# SNMP v3 authentication protocols
SNMP_AUTH_PROTOCOLS: Final = {
    "none": "usmNoAuthProtocol",
    "md5": "usmHMACMD5AuthProtocol", 
    "sha": "usmHMACSHAAuthProtocol",
    "sha224": "usmHMAC128SHA224AuthProtocol",
    "sha256": "usmHMAC192SHA256AuthProtocol",
    "sha384": "usmHMAC256SHA384AuthProtocol",
    "sha512": "usmHMAC384SHA512AuthProtocol"
}

# SNMP v3 privacy protocols  
SNMP_PRIV_PROTOCOLS: Final = {
    "none": "usmNoPrivProtocol",
    "des": "usmDESPrivProtocol",
    "3des": "usm3DESEDEPrivProtocol", 
    "aes128": "usmAesCfb128Protocol",
    "aes192": "usmAesCfb192Protocol",
    "aes256": "usmAesCfb256Protocol"
}

# Dell iDRAC SNMP OIDs - Updated with verified working OIDs from comprehensive discovery
IDRAC_OIDS: Final = {
    # Basic power and thermal monitoring (verified)
    "power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
    "temp_inlet": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.1",
    "temp_outlet": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.2",
    "temp_cpu_base": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
    "fan_base": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
    "psu_status_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1",
    "psu_voltage_base": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1",
    "psu_amperage_base": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    # System health and status
    "system_health": "1.3.6.1.4.1.674.10892.5.2.1.0",
    # Power state OIDs - tested and working alternatives
    "system_power_state": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.1",      # WORKING: returns 1 (power on)
    "system_power_state_alt": "1.3.6.1.4.1.674.10892.5.4.200.10.1.6.1",    # WORKING: returns 3 (system state)
    # Chassis intrusion - using Dell's chassis security breach status
    "system_intrusion": "1.3.6.1.4.1.674.10892.5.4.300.70.1.25.1.1",
    "system_intrusion_alt": "1.3.6.1.4.1.674.10892.5.4.300.70.1.24.1.1",
    # PSU redundancy - tested working OID
    "psu_redundancy": "1.3.6.1.4.1.674.10892.5.4.600.10.1.8.1.1",          # WORKING: returns 3 (redundancy status)
    "psu_redundancy_alt": "1.3.6.1.4.1.674.10892.5.4.600.10.1.9.1.1",      # Original (not working on test system)
    # Memory health - requires double indexing (.1.X format)  
    "memory_health_base": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1",       # WORKING: memoryDeviceStatus (requires .1.X indexing)
    "memory_health_base_alt": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5.1",   # WORKING: alternative status column (requires .1.X indexing)
    # Control OIDs (for switches) - updated with working alternatives
    "power_control": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.1",          # WORKING: power control (index 1 instead of 3)
    "identify_led": "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.1",           # Updated index (1 instead of 3)
    "safe_mode": "1.3.6.1.4.1.674.10892.5.4.300.70.1.11.1.1",              # Updated index (1 instead of 3)
    
    # Temperature probe monitoring (verified against official MIB)
    "temperature_probe_status": "1.3.6.1.4.1.674.10892.5.4.700.20.1.5.1",   # temperatureProbeStatus
    "temperature_probe_reading": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",  # temperatureProbeReading
    "cooling_device_status": "1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1",      # coolingDeviceStatus
    
    # Storage and RAID monitoring OIDs
    "virtual_disk_state": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4",      # Virtual disk state
    "virtual_disk_layout": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.13",    # Virtual disk layout type
    "virtual_disk_size": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.6",       # Virtual disk size
    "virtual_disk_name": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2",       # Virtual disk name
    "physical_disk_state": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.4",     # Physical disk state
    "physical_disk_capacity": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.11", # Physical disk capacity
    "physical_disk_used_space": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.17", # Physical disk used space
    "physical_disk_serial": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.7",    # Physical disk serial number
    "controller_state": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.38",       # Storage controller state
    "controller_battery_state": "1.3.6.1.4.1.674.10892.5.5.1.20.130.15.1.4", # Controller battery state
    
    # System identification OIDs (verified against actual iDRAC testing)
    "system_model_name": "1.3.6.1.4.1.674.10892.5.4.300.10.1.7.1",         # chassisSystemName - WORKING: "Main System Chassis"
    "system_model_name_alt": "1.3.6.1.4.1.674.10892.5.4.300.10.1.9.1.1",   # chassisModelName - original (not working on test system)
    "system_model_name_alt2": "1.3.6.1.4.1.674.10892.5.1.3.12.0",          # systemModelName - original (not working on test system)
    "system_service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",               # systemServiceTag - verified correct
    "system_bios_version": "1.3.6.1.4.1.674.10892.5.1.3.7.0",              # systemBIOSReleaseDateName - WORKING alternative
    "cpu_brand": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.23.1.1",             # processorDeviceBrandName - verified correct
    "cpu_max_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.11.1.1",         # processorDeviceMaximumSpeed - verified correct
    "cpu_current_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.12.1.1",     # processorDeviceCurrentSpeed - verified correct
    "controller_rollup_status": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.37", # Controller rollup status (combined health)
    "controller_name": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.2",           # Controller name/model
    "controller_firmware": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.8",       # Controller firmware version
    "controller_cache_size": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.9",      # Controller cache memory size (verified: returns 2048)
    "controller_rebuild_rate": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.48",    # Controller rebuild rate setting (verified)
    
    # Enhanced memory monitoring (verified from discovery)
    "memory_device_type": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7.1",             # Memory device type (verified: returns 26)
    "memory_device_size": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1",            # Memory device size (verified: returns 16777216 KB)
    "memory_device_speed": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.27.1",           # Memory device speed (verified: returns 1867 MHz)
    "memory_device_manufacturer": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.21.1",    # Memory manufacturer (verified: Hynix Semiconductor)
    "memory_device_part_number": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.22.1",     # Memory part number (verified: HMA82GR7MFR8N-UH)
    "memory_device_serial": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.23.1",          # Memory serial number (verified)
    "memory_device_bank": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.10.1",            # Memory bank location (verified: A/B)
    "memory_device_location": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1",         # Memory device location (verified: DIMM.Socket.A1, etc.)
    
    # System voltage monitoring (verified from discovery)
    "system_voltage_cpu1_vcore": "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.1",    # CPU1 VCORE voltage status (verified: returns 1)
    "system_voltage_cpu2_vcore": "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.2",    # CPU2 VCORE voltage status (verified: returns 1)
    "system_voltage_3v3": "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.3",           # System Board 3.3V status (verified: returns 1)
    "system_voltage_cpu1_name": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.1",      # CPU1 VCORE name (verified: "CPU1 VCORE PG")
    "system_voltage_cpu2_name": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.2",      # CPU2 VCORE name (verified: "CPU2 VCORE PG")
    "system_voltage_3v3_name": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.3",       # 3.3V rail name (verified: "System Board 3.3V PG")
    
    # Enhanced power consumption monitoring (verified from discovery)
    "power_consumption_system": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",       # REAL-TIME system power consumption in watts (verified: ~140W)
    "power_consumption_psu1": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.1",         # PSU1 current draw (verified: 12A)
    "power_consumption_psu2": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.2",         # PSU2 current draw (verified: 2A)
    "power_consumption_max_watts": "1.3.6.1.4.1.674.10892.5.4.600.30.1.10.1.3",    # Maximum/total system power capacity (verified: 644W)
    "power_consumption_warning_threshold": "1.3.6.1.4.1.674.10892.5.4.600.30.1.11.1.3", # Power warning threshold (verified: 588W)
    "power_psu1_name": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1.1",                # PSU1 name (verified: "PS1 Current 1")
    "power_psu2_name": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1.2",                # PSU2 name (verified: "PS2 Current 2")
    "power_system_name": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1.3",              # System power name (verified: "System Board Pwr Consumption")
    
    # Fan monitoring with names (verified from discovery)
    "fan_name_base": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1",                    # Fan names (verified: "System Board Fan1", etc.)
    "fan_fqdd_base": "1.3.6.1.4.1.674.10892.5.4.700.12.1.19.1",                   # Fan FQDD (verified: "Fan.Embedded.1", etc.)
    "fan_min_warning": "1.3.6.1.4.1.674.10892.5.4.700.12.1.13.1",                 # Fan minimum warning threshold (verified: 360 RPM)
    "fan_max_warning": "1.3.6.1.4.1.674.10892.5.4.700.12.1.12.1",                 # Fan maximum warning threshold (verified: 600 RPM)
    
    # Temperature monitoring with names (verified from discovery)
    "temp_name_base": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1",                   # Temperature probe names (verified: "System Board Inlet Temp", etc.)
    "temp_upper_critical": "1.3.6.1.4.1.674.10892.5.4.700.20.1.10.1",             # Upper critical threshold (verified)
    "temp_upper_warning": "1.3.6.1.4.1.674.10892.5.4.700.20.1.11.1",              # Upper warning threshold (verified)
    "temp_lower_critical": "1.3.6.1.4.1.674.10892.5.4.700.20.1.13.1",             # Lower critical threshold (verified)
    "temp_lower_warning": "1.3.6.1.4.1.674.10892.5.4.700.20.1.12.1",              # Lower warning threshold (verified)
    
    # Enhanced physical disk monitoring (verified from discovery)
    "physical_disk_name": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.2",             # Physical disk name (verified: "Physical Disk 0:1:0")
    "physical_disk_vendor": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.3",           # Physical disk vendor (verified: "TOSHIBA", "SEAGATE")
    "physical_disk_product_id": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.6",       # Physical disk product ID (verified: "AL13SEB300")
    "physical_disk_revision": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.8",         # Physical disk firmware revision (verified: "DE11")
    "physical_disk_size_mb": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.11",         # Physical disk size in MB (verified: 285568, 571776)
    "physical_disk_fqdd": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.27",            # Physical disk FQDD (verified)
    
    # PSU detailed monitoring (verified from discovery)
    "psu_name_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.8.1",                    # PSU names (verified: "PS1 Status", "PS2 Status")
    "psu_fqdd_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.15.1",                   # PSU FQDD (verified: "PSU.Slot.1", "PSU.Slot.2")
    "psu_max_output_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.6.1",              # PSU maximum output (verified: 4950W)
    "psu_input_voltage_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.4.1",           # PSU input voltage (verified: 242V)
    "psu_rated_output_base": "1.3.6.1.4.1.674.10892.5.4.600.12.1.14.1",           # PSU rated output (verified: 5940W)
}

# SNMP base OIDs for discovery - Updated with verified working OIDs
SNMP_WALK_OIDS: Final = {
    "fans": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
    "cpu_temps": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
    "psu_status": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1",
    "psu_voltage": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1",
    "psu_amperage": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    "memory_health": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1",
    # Storage discovery OIDs
    "virtual_disks": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4",
    "physical_disks": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.4",
    "storage_controllers": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.38",
    # New discovery OIDs (verified from comprehensive discovery)
    "detailed_memory": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1",               # Memory device size for discovery
    "system_voltages": "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1",                # System voltage probes
    "power_consumption": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",               # Power consumption sensors
}

# Memory health status mapping (verified from Dell documentation)
MEMORY_HEALTH_STATUS: Final = {
    1: "other",
    2: "ready",      # Changed from "unknown" - this is actually ready/healthy state
    3: "ok",         # Normal/healthy state  
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

# PSU status mapping (verified from Dell documentation)
PSU_STATUS: Final = {
    1: "other",
    2: "unknown", 
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable"
}

# Physical disk status mapping (verified from Dell documentation)
PHYSICAL_DISK_STATUS: Final = {
    1: "ready",
    2: "failed",
    3: "online",
    4: "offline",
    5: "degraded",
    6: "verifying",
    7: "incompatible",
    8: "removed",
    9: "clear",
    10: "smart_alert_pending",
    11: "foreign"
}

# Virtual disk status mapping (corrected based on user feedback)
VIRTUAL_DISK_STATUS: Final = {
    1: "ready",
    2: "optimal",  # Fixed: was "failed" but user reported healthy disk shows state 2
    3: "online",
    4: "offline",
    5: "degraded",
    6: "verifying",
    7: "background_init",
    8: "resynching"
}