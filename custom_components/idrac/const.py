"""Constants for the Dell iDRAC integration."""
from typing import Final

DOMAIN: Final = "idrac"

# Configuration constants
CONF_PORT: Final = "port"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_PORT: Final = 443
DEFAULT_SCAN_INTERVAL: Final = 30

# Redfish status mappings for Health values
REDFISH_HEALTH_STATUS: Final = {
    "OK": "ok",
    "Warning": "warning", 
    "Critical": "critical",
    None: "unknown"
}

# Redfish state mappings for State values
REDFISH_STATE_STATUS: Final = {
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
POWER_STATE_STATUS: Final = {
    "On": "on",
    "Off": "off",
    "PoweringOn": "powering_on",
    "PoweringOff": "powering_off",
    None: "unknown"
}