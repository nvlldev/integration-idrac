"""Constants for the Dell iDRAC integration."""
from typing import Final

DOMAIN: Final = "idrac"

# Configuration constants
CONF_COMMUNITY: Final = "community"
CONF_DISCOVERED_FANS: Final = "discovered_fans"
CONF_DISCOVERED_CPUS: Final = "discovered_cpus"
CONF_DISCOVERED_PSUS: Final = "discovered_psus"
CONF_DISCOVERED_VOLTAGE_PROBES: Final = "discovered_voltage_probes"
CONF_DISCOVERED_MEMORY: Final = "discovered_memory"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_PORT: Final = 161
DEFAULT_COMMUNITY: Final = "public"
DEFAULT_SCAN_INTERVAL: Final = 30

# Dell iDRAC SNMP OIDs
IDRAC_OIDS: Final = {
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
    # Power state OIDs - using Dell's chassis power state OIDs  
    "system_power_state": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.3",
    "system_power_state_alt": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.1",
    # Chassis intrusion - using Dell's chassis security breach status
    "system_intrusion": "1.3.6.1.4.1.674.10892.5.4.300.70.1.25.1.1",
    "system_intrusion_alt": "1.3.6.1.4.1.674.10892.5.4.300.70.1.24.1.1",
    # PSU redundancy - using Dell's power supply redundancy status
    "psu_redundancy": "1.3.6.1.4.1.674.10892.5.4.600.10.1.9.1.1",
    "psu_redundancy_alt": "1.3.6.1.4.1.674.10892.5.4.600.10.1.8.1.1",
    # Memory health (corrected OID)
    "memory_health_base": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5",
    # Control OIDs (for switches)
    "power_control": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1.3",
    "identify_led": "1.3.6.1.4.1.674.10892.5.4.300.70.1.10.1.3",
    "safe_mode": "1.3.6.1.4.1.674.10892.5.4.300.70.1.11.1.3",
}

# SNMP base OIDs for discovery
SNMP_WALK_OIDS: Final = {
    "fans": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
    "cpu_temps": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
    "psu_status": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1",
    "psu_voltage": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1",
    "psu_amperage": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    "memory_health": "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5",
}