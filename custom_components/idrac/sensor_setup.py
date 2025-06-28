"""Sensor setup utilities for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfPower, UnitOfTemperature, REVOLUTIONS_PER_MINUTE, PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from .coordinator_snmp import SNMPDataUpdateCoordinator
    from .coordinator_redfish import RedfishDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Sensor configuration mapping
SENSOR_CONFIGS = {
    # Standard category-based sensors
    "temperatures": {
        "sensor_class": "IdracTemperatureSensor",
        "preferred_coordinator": "snmp",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
    "fans": {
        "sensor_class": "IdracFanSpeedSensor", 
        "preferred_coordinator": "snmp",
        "unit": REVOLUTIONS_PER_MINUTE,
        "device_class": None,
    },
    "voltages": {
        "sensor_class": "IdracVoltageSensor",
        "preferred_coordinator": "snmp", 
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
    },
    "memory": {
        "sensor_class": "IdracMemorySensor",
        "preferred_coordinator": "snmp",
        "unit": "GB", 
        "device_class": None,
    },
    "intrusion_detection": {
        "sensor_class": "IdracIntrusionSensor",
        "preferred_coordinator": "snmp",
        "unit": None,
        "device_class": None,
    },
    "battery": {
        "sensor_class": "IdracBatterySensor",
        "preferred_coordinator": "snmp",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.BATTERY,
    },
    "processors": {
        "sensor_class": "IdracProcessorSensor", 
        "preferred_coordinator": "snmp",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
    },
}

# Single instance sensors
SINGLE_SENSORS = [
    {
        "class": "IdracPowerConsumptionSensor",
        "category": "power_consumption",
        "preferred_coordinator": "snmp",
    },
    {
        "class": "IdracMemorySensor", 
        "category": "memory",
        "preferred_coordinator": "snmp",
    },
    {
        "class": "IdracFirmwareVersionSensor",
        "category": "manager_info", 
        "preferred_coordinator": "redfish",
    },
    {
        "class": "IdracDateTimeSensor",
        "category": "manager_info",
        "preferred_coordinator": "redfish", 
    },
]

# Aggregate sensors (require specific data patterns)
AGGREGATE_SENSORS = [
    {
        "class": "IdracAverageCpuTemperatureSensor",
        "requires_category": "temperatures",
        "requires_pattern": "cpu",
    },
    {
        "class": "IdracAverageFanSpeedSensor", 
        "requires_category": "fans",
        "requires_pattern": None,
    },
    {
        "class": "IdracTemperatureDeltaSensor",
        "requires_category": "temperatures", 
        "requires_pattern": ["inlet", "outlet"],
    },
]


def get_coordinator_for_category(
    category: str,
    snmp_coordinator: SNMPDataUpdateCoordinator,
    redfish_coordinator: RedfishDataUpdateCoordinator,
    preferred: str = "snmp"
) -> SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator | None:
    """Get the best coordinator for a data category."""
    
    # Check preferred coordinator first
    if preferred == "snmp" and snmp_coordinator and snmp_coordinator.data:
        if category in snmp_coordinator.data and snmp_coordinator.data[category]:
            return snmp_coordinator
    elif preferred == "redfish" and redfish_coordinator and redfish_coordinator.data:
        if category in redfish_coordinator.data and redfish_coordinator.data[category]:
            return redfish_coordinator
    
    # Fallback to any coordinator with data
    if snmp_coordinator and snmp_coordinator.data:
        if category in snmp_coordinator.data and snmp_coordinator.data[category]:
            return snmp_coordinator
            
    if redfish_coordinator and redfish_coordinator.data:
        if category in redfish_coordinator.data and redfish_coordinator.data[category]:
            return redfish_coordinator
    
    return None


def log_coordinator_status(snmp_coordinator, redfish_coordinator):
    """Log the status of both coordinators."""
    def get_categories(coord):
        if coord and coord.data:
            return [k for k, v in coord.data.items() if v]
        return []
    
    snmp_categories = get_categories(snmp_coordinator)
    redfish_categories = get_categories(redfish_coordinator)
    
    if snmp_categories:
        _LOGGER.info("SNMP coordinator: %d categories (%s)", 
                     len(snmp_categories), ", ".join(snmp_categories))
    else:
        _LOGGER.warning("SNMP coordinator: no data available")
        
    if redfish_categories:
        _LOGGER.info("Redfish coordinator: %d categories (%s)", 
                     len(redfish_categories), ", ".join(redfish_categories))
    else:
        _LOGGER.warning("Redfish coordinator: no data available")


def count_pattern_matches(data: dict, pattern: str) -> int:
    """Count items matching a pattern in their name."""
    count = 0
    for item in data.values():
        name = item.get("name", "").lower()
        if pattern in name:
            count += 1
    return count


def has_temperature_patterns(temp_data: dict, patterns: list[str]) -> bool:
    """Check if temperature data has required patterns."""
    for pattern in patterns:
        found = any(pattern in item.get("name", "").lower() for item in temp_data.values())
        if not found:
            return False
    return True