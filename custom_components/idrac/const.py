"""Constants for the Dell iDRAC integration."""
from typing import Final

DOMAIN: Final = "idrac"

CONF_NUM_FANS: Final = "num_fans"
CONF_NUM_CPUS: Final = "num_cpus"
CONF_DISCOVERED_FANS: Final = "discovered_fans"
CONF_DISCOVERED_CPUS: Final = "discovered_cpus"

DEFAULT_PORT: Final = 161
DEFAULT_COMMUNITY: Final = "public"
DEFAULT_SCAN_INTERVAL: Final = 30

IDRAC_OIDS: Final = {
    "power": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
    "temp_inlet": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.1",
    "temp_outlet": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.2",
    "temp_cpu_base": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
    "fan_base": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
}

SNMP_WALK_OIDS: Final = {
    "fans": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
    "cpu_temps": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
}