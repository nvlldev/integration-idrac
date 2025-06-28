"""Sensor platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, REDFISH_HEALTH_STATUS
from .coordinator_snmp import SNMPDataUpdateCoordinator
from .coordinator_redfish import RedfishDataUpdateCoordinator
from .entity_base import IdracEntityBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC sensors."""
    from .sensor_setup import (
        get_coordinator_for_category, 
        log_coordinator_status,
        count_pattern_matches,
        has_temperature_patterns
    )
    
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    snmp_coordinator = coordinators["snmp"]
    redfish_coordinator = coordinators["redfish"]
    
    entities: list[IdracSensor] = []
    
    # Log coordinator status
    log_coordinator_status(snmp_coordinator, redfish_coordinator)
    
    # Category-based sensors with item data
    category_sensors = [
        ("temperatures", IdracTemperatureSensor),
        ("fans", IdracFanSpeedSensor),
        ("voltages", IdracVoltageSensor),
        # ("intrusion_detection", IdracIntrusionSensor), # Moved to binary_sensor.py as System Board Intrusion Detection
        # ("battery", IdracBatterySensor), # Moved to binary_sensor.py as IdracBatteryHealthBinarySensor
        ("processors", IdracProcessorSensor),
    ]
    
    for category, sensor_class in category_sensors:
        coordinator = get_coordinator_for_category(category, snmp_coordinator, redfish_coordinator, "snmp")
        if coordinator and coordinator.data and category in coordinator.data:
            items = coordinator.data[category]
            if items:
                _LOGGER.info("Creating %d %s sensors using %s coordinator", 
                           len(items), category, type(coordinator).__name__)
                for item_id, item_data in items.items():
                    entities.append(sensor_class(coordinator, config_entry, item_id, item_data))
    
    # Memory health sensors removed - now handled by binary_sensor.py as DIMM Socket Health binary sensors
    
    # PSU specific sensors removed per user request - no PSU voltage or output power sensors
    
    # Single instance sensors
    single_sensors = [
        ("power_consumption", IdracPowerConsumptionSensor, "snmp"),
        ("memory", IdracMemorySensor, "snmp"),
    ]
    
    for category, sensor_class, preferred in single_sensors:
        coordinator = get_coordinator_for_category(category, snmp_coordinator, redfish_coordinator, preferred)
        if coordinator and coordinator.data and category in coordinator.data and coordinator.data[category]:
            entities.append(sensor_class(coordinator, config_entry))
            _LOGGER.debug("Created %s using %s coordinator", sensor_class.__name__, type(coordinator).__name__)
    
    # System information sensors (typically Redfish)
    system_coordinator = get_coordinator_for_category("system_info", snmp_coordinator, redfish_coordinator, "redfish")
    if system_coordinator and system_coordinator.data and "system_info" in system_coordinator.data:
        system_sensors = [
            IdracProcessorCountSensor,
            IdracProcessorModelSensor, 
            IdracMemoryMirroringSensor,
            IdracProcessorStatusSensor,
            IdracMemoryStatusSensor,
            IdracMemoryTypeSensor,
            IdracProcessorMaxSpeedSensor,
            IdracProcessorCurrentSpeedSensor,
        ]
        for sensor_class in system_sensors:
            entities.append(sensor_class(system_coordinator, config_entry))
    
    # Manager information sensors (Redfish only)
    manager_coordinator = get_coordinator_for_category("manager_info", snmp_coordinator, redfish_coordinator, "redfish")
    if manager_coordinator and manager_coordinator.data and "manager_info" in manager_coordinator.data:
        manager_sensors = [IdracFirmwareVersionSensor, IdracDateTimeSensor]
        for sensor_class in manager_sensors:
            entities.append(sensor_class(manager_coordinator, config_entry))
    
    # Power consumption aggregate sensors removed per user request
    
    # Aggregate sensors with pattern requirements
    temp_coordinator = get_coordinator_for_category("temperatures", snmp_coordinator, redfish_coordinator, "snmp")
    if temp_coordinator and temp_coordinator.data and "temperatures" in temp_coordinator.data:
        temp_data = temp_coordinator.data["temperatures"]
        
        # CPU temperature average
        if count_pattern_matches(temp_data, "cpu") > 0:
            entities.append(IdracAverageCpuTemperatureSensor(temp_coordinator, config_entry))
        
        # Temperature delta (inlet/outlet)
        inlet_found = any("inlet" in item.get("name", "").lower() or "intake" in item.get("name", "").lower() or "ambient" in item.get("name", "").lower() for item in temp_data.values())
        outlet_found = any("outlet" in item.get("name", "").lower() or "exhaust" in item.get("name", "").lower() or "exit" in item.get("name", "").lower() for item in temp_data.values())
        
        _LOGGER.debug("Temperature Rise sensor check: inlet_found=%s, outlet_found=%s", inlet_found, outlet_found)
        if inlet_found and outlet_found:
            entities.append(IdracTemperatureDeltaSensor(temp_coordinator, config_entry))
            _LOGGER.info("Created Temperature Rise sensor with inlet and outlet temperature sensors")
        else:
            _LOGGER.debug("Temperature Rise sensor not created - missing inlet (%s) or outlet (%s) sensors", inlet_found, outlet_found)
    
    # Average fan speed
    fan_coordinator = get_coordinator_for_category("fans", snmp_coordinator, redfish_coordinator, "snmp")
    if fan_coordinator and fan_coordinator.data and "fans" in fan_coordinator.data and fan_coordinator.data["fans"]:
        entities.append(IdracAverageFanSpeedSensor(fan_coordinator, config_entry))

    # Add response time sensors for each coordinator
    if snmp_coordinator:
        entities.append(IdracSnmpResponseTimeSensor(snmp_coordinator, config_entry))
        _LOGGER.debug("Created SNMP response time sensor")
    
    if redfish_coordinator:
        entities.append(IdracRedfishResponseTimeSensor(redfish_coordinator, config_entry))
        _LOGGER.debug("Created Redfish response time sensor")

    if entities:
        _LOGGER.info("Successfully created %d sensor entities for iDRAC", len(entities))
    else:
        _LOGGER.error("No sensor entities created - check SNMP/Redfish connectivity and sensor discovery")
    
    async_add_entities(entities)




class IdracSensor(IdracEntityBase, SensorEntity):
    """Common base class for Dell iDRAC sensors."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, sensor_key, sensor_name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if unit:  # Only set state class if we have a unit
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._entity_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.native_value is not None


class IdracPowerConsumptionSensor(IdracSensor):
    """Power consumption sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power consumption sensor."""
        super().__init__(coordinator, config_entry, "power_consumption", "System Power Consumption")
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Primary power measurement - not diagnostic
        self._attr_icon = "mdi:flash"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        power_data = self.coordinator.data.get("power_consumption", {})
        return power_data.get("consumed_watts")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        power_data = self.coordinator.data.get("power_consumption", {})
        return {
            "capacity_watts": power_data.get("capacity_watts"),
            "average_consumed_watts": power_data.get("average_consumed_watts"),
            "max_consumed_watts": power_data.get("max_consumed_watts"),
            "min_consumed_watts": power_data.get("min_consumed_watts"),
        }


class IdracTemperatureSensor(IdracSensor):
    """Temperature sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        temp_id: str,
        temp_data: dict,
    ) -> None:
        """Initialize the temperature sensor."""
        # Improve naming for CPU temperature sensors
        sensor_name = temp_data.get("name", "")
        if sensor_name and "cpu" in sensor_name.lower():
            # Extract CPU number for cleaner naming (e.g., "CPU1 Temp" -> "CPU 1 Temperature")
            import re
            cpu_match = re.search(r'cpu\s*(\d+)', sensor_name.lower())
            if cpu_match:
                cpu_num = cpu_match.group(1)
                name = f"CPU {cpu_num} Temperature"
            else:
                name = sensor_name
        else:
            name = sensor_name or f"Temperature {temp_id}"
        super().__init__(coordinator, config_entry, f"temperature_{temp_id}", name)
        self.temp_id = temp_id
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Environmental measurement - not diagnostic
        self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        temp_data = self.coordinator.data.get("temperatures", {}).get(self.temp_id, {})
        return temp_data.get("temperature")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        temp_data = self.coordinator.data.get("temperatures", {}).get(self.temp_id, {})
        return {
            "status": REDFISH_HEALTH_STATUS.get(temp_data.get("status")),
            "upper_threshold_critical": temp_data.get("upper_threshold_critical"),
            "upper_threshold_non_critical": temp_data.get("upper_threshold_non_critical"),
        }


class IdracFanSpeedSensor(IdracSensor):
    """Fan speed sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        fan_id: str,
        fan_data: dict,
    ) -> None:
        """Initialize the fan sensor."""
        # Improve fan naming to handle various patterns
        sensor_name = fan_data.get("name", "")
        if sensor_name:
            # Handle "System Board Fan1" -> "System Fan 1 Speed"
            import re
            if "system board fan" in sensor_name.lower():
                fan_match = re.search(r'fan\s*(\d+)', sensor_name.lower())
                if fan_match:
                    fan_num = fan_match.group(1)
                    name = f"System Fan {fan_num} Speed"
                else:
                    name = f"{sensor_name} Speed"
            elif not sensor_name.lower().endswith('speed'):
                name = f"{sensor_name} Speed"
            else:
                name = sensor_name
        else:
            # Extract numeric index from fan_id for cleaner naming
            fan_index = fan_id.replace('fan_', '') if fan_id.startswith('fan_') else fan_id
            name = f"System Fan {fan_index} Speed"
        super().__init__(coordinator, config_entry, f"fan_{fan_id}", name)
        self.fan_id = fan_id
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Environmental measurement - not diagnostic
        self._attr_icon = "mdi:fan"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        fan_data = self.coordinator.data.get("fans", {}).get(self.fan_id, {})
        
        # Prefer RPM over percentage
        if fan_data.get("speed_rpm") is not None:
            return fan_data.get("speed_rpm")
        return fan_data.get("speed_percent")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if not self.coordinator.data:
            return None
        fan_data = self.coordinator.data.get("fans", {}).get(self.fan_id, {})
        
        if fan_data.get("speed_rpm") is not None:
            return REVOLUTIONS_PER_MINUTE
        return PERCENTAGE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        fan_data = self.coordinator.data.get("fans", {}).get(self.fan_id, {})
        return {
            "status": REDFISH_HEALTH_STATUS.get(fan_data.get("status")),
            "speed_rpm": fan_data.get("speed_rpm"),
            "speed_percent": fan_data.get("speed_percent"),
        }


class IdracVoltageSensor(IdracSensor):
    """Voltage sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        voltage_id: str,
        voltage_data: dict,
    ) -> None:
        """Initialize the voltage sensor."""
        name = voltage_data.get("name", f"Voltage {voltage_id}")
        super().__init__(coordinator, config_entry, f"voltage_{voltage_id}", name)
        self.voltage_id = voltage_id
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Electrical measurement - not diagnostic
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        voltage_data = self.coordinator.data.get("voltages", {}).get(self.voltage_id, {})
        return voltage_data.get("reading_volts")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        voltage_data = self.coordinator.data.get("voltages", {}).get(self.voltage_id, {})
        return {
            "status": REDFISH_HEALTH_STATUS.get(voltage_data.get("status")),
            "upper_threshold_critical": voltage_data.get("upper_threshold_critical"),
            "upper_threshold_non_critical": voltage_data.get("upper_threshold_non_critical"),
            "lower_threshold_critical": voltage_data.get("lower_threshold_critical"),
            "lower_threshold_non_critical": voltage_data.get("lower_threshold_non_critical"),
        }


class IdracMemorySensor(IdracSensor):
    """Memory sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the memory sensor."""
        super().__init__(coordinator, config_entry, "memory_total", "Total System Memory")
        self._attr_native_unit_of_measurement = "GB"
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:memory"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_gb")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_gb") is not None


class IdracProcessorCountSensor(IdracSensor):
    """Processor count sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor count sensor."""
        super().__init__(coordinator, config_entry, "processor_count", "Total Processors")
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:cpu-64-bit"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_count")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_count") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return {
            "processor_model": system_info.get("processor_model"),
        }



# Memory health sensors removed - now handled by binary_sensor.py as DIMM Socket Health binary sensors


# PSU status sensors are handled by binary sensors - regular PSU status sensor class removed


# Intrusion detection sensors moved to binary_sensor.py as System Board Intrusion Detection binary sensors


# Battery sensor moved to binary_sensor.py as IdracBatteryHealthBinarySensor


class IdracProcessorSensor(IdracSensor):
    """Processor sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        processor_id: str,
        processor_data: dict[str, Any],
    ) -> None:
        """Initialize the processor sensor."""
        processor_name = processor_data.get("name", f"Processor {processor_id}")
        super().__init__(coordinator, config_entry, f"processor_{processor_id}", f"{processor_name} Health")
        self.processor_id = processor_id
        self._attr_entity_category = None

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "processors" not in self.coordinator.data:
            return None
        processor_data = self.coordinator.data["processors"].get(self.processor_id)
        if not processor_data:
            return None
        return processor_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "ok":
            return "mdi:chip"
        elif status in ["non_critical", "critical", "non_recoverable"]:
            return "mdi:chip-alert"
        else:
            return "mdi:chip-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data or "processors" not in self.coordinator.data:
            return None
        processor_data = self.coordinator.data["processors"].get(self.processor_id)
        if not processor_data:
            return None
        return {
            "reading": processor_data.get("reading"),
            "name": processor_data.get("name"),
        }


class IdracFirmwareVersionSensor(IdracSensor):
    """iDRAC firmware version sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "idrac_firmware_version", "iDRAC Firmware Version")
        self._attr_unique_id = f"{coordinator.host}_idrac_firmware_version"
        self._attr_entity_category = None
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        if not self.coordinator.data or "manager_info" not in self.coordinator.data:
            return None
        return self.coordinator.data["manager_info"].get("firmware_version")


class IdracDateTimeSensor(IdracSensor):
    """iDRAC system date/time sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "system_datetime", "System Date Time")
        self._attr_unique_id = f"{coordinator.host}_system_datetime"
        self._attr_entity_category = None
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str | None:
        """Return the system date/time."""
        if not self.coordinator.data or "manager_info" not in self.coordinator.data:
            return None
        return self.coordinator.data["manager_info"].get("datetime")


# PSU input power sensor removed as requested


# PSU output power and input voltage sensors removed per user request


# Power aggregate sensors (Average, Min, Max) removed per user request


class IdracSnmpResponseTimeSensor(IdracSensor):
    """SNMP response time sensor showing how long SNMP data collection takes."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the SNMP response time sensor."""
        super().__init__(coordinator, config_entry, "snmp_response_time", "SNMP Response Time")
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "s"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:timer-outline"

    @property
    def native_value(self) -> float | None:
        """Return the SNMP data collection time in seconds."""
        return getattr(self.coordinator, 'last_update_duration', None)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about SNMP data collection."""
        attributes = {
            "protocol": "SNMP",
            "coordinator_type": type(self.coordinator).__name__,
        }
        
        # Add last update information
        if hasattr(self.coordinator, 'last_update_success'):
            attributes["last_update_success"] = self.coordinator.last_update_success
        if hasattr(self.coordinator, 'last_exception'):
            attributes["last_exception"] = str(self.coordinator.last_exception) if self.coordinator.last_exception else None
            
        return attributes


class IdracRedfishResponseTimeSensor(IdracSensor):
    """Redfish response time sensor showing how long Redfish data collection takes."""
    
    def __init__(self, coordinator: RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the Redfish response time sensor."""
        super().__init__(coordinator, config_entry, "redfish_response_time", "Redfish Response Time")
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "s"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:timer-outline"

    @property
    def native_value(self) -> float | None:
        """Return the Redfish data collection time in seconds."""
        return getattr(self.coordinator, 'last_update_duration', None)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about Redfish data collection."""
        attributes = {
            "protocol": "Redfish",
            "coordinator_type": type(self.coordinator).__name__,
        }
        
        # Add last update information
        if hasattr(self.coordinator, 'last_update_success'):
            attributes["last_update_success"] = self.coordinator.last_update_success
        if hasattr(self.coordinator, 'last_exception'):
            attributes["last_exception"] = str(self.coordinator.last_exception) if self.coordinator.last_exception else None
            
        return attributes


class IdracAverageCpuTemperatureSensor(IdracSensor):
    """Overall CPU temperature averaged across all processor temperature sensors."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "average_cpu_temperature", "CPU Average Temperature")
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Primary thermal measurement
        self._attr_icon = "mdi:thermometer-chevron-up"

    @property
    def native_value(self) -> float | None:
        """Return the average CPU temperature."""
        if not self.coordinator.data or "temperatures" not in self.coordinator.data:
            return None
        
        temperatures = self.coordinator.data["temperatures"]
        cpu_temps = []
        
        # Find all CPU temperature sensors
        for temp_id, temp_data in temperatures.items():
            temp_name = temp_data.get("name", "").lower()
            temp_value = temp_data.get("temperature")
            
            # Include sensors that are clearly CPU-related
            if temp_value is not None and any(keyword in temp_name for keyword in 
                ["cpu", "processor", "proc"]):
                cpu_temps.append(temp_value)
        
        if not cpu_temps:
            return None
            
        return round(sum(cpu_temps) / len(cpu_temps), 1)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about CPU temperatures."""
        if not self.coordinator.data or "temperatures" not in self.coordinator.data:
            return None
        
        temperatures = self.coordinator.data["temperatures"]
        cpu_temps = []
        cpu_sensors = []
        
        for temp_id, temp_data in temperatures.items():
            temp_name = temp_data.get("name", "").lower()
            temp_value = temp_data.get("temperature")
            
            if temp_value is not None and any(keyword in temp_name for keyword in 
                ["cpu", "processor", "proc"]):
                cpu_temps.append(temp_value)
                cpu_sensors.append(temp_data.get("name", temp_id))
        
        if not cpu_temps:
            return None
            
        return {
            "sensor_count": len(cpu_temps),
            "min_temperature": round(min(cpu_temps), 1),
            "max_temperature": round(max(cpu_temps), 1),
            "cpu_sensors": cpu_sensors,
        }


class IdracAverageFanSpeedSensor(IdracSensor):
    """System-wide fan performance showing average speed across all cooling fans."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "average_fan_speed", "System Fan Speed Average")
        self._attr_native_unit_of_measurement = REVOLUTIONS_PER_MINUTE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Primary environmental measurement
        self._attr_icon = "mdi:fan"

    @property
    def native_value(self) -> float | None:
        """Return the average fan speed in RPM."""
        if not self.coordinator.data or "fans" not in self.coordinator.data:
            return None
        
        fans = self.coordinator.data["fans"]
        fan_speeds = []
        
        # Collect all fan speeds (prefer RPM over percentage)
        for fan_id, fan_data in fans.items():
            rpm_speed = fan_data.get("speed_rpm")
            percent_speed = fan_data.get("speed_percent")
            
            # Prefer RPM reading over percentage
            if rpm_speed is not None and rpm_speed > 0:
                fan_speeds.append(rpm_speed)
            elif percent_speed is not None and percent_speed > 0:
                # Convert percentage to approximate RPM (assuming ~3000 RPM max)
                estimated_rpm = (percent_speed / 100) * 3000
                fan_speeds.append(estimated_rpm)
        
        if not fan_speeds:
            return None
            
        return round(sum(fan_speeds) / len(fan_speeds))
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about fan speeds."""
        if not self.coordinator.data or "fans" not in self.coordinator.data:
            return None
        
        fans = self.coordinator.data["fans"]
        fan_speeds = []
        fan_names = []
        rpm_count = 0
        percent_count = 0
        
        for fan_id, fan_data in fans.items():
            rpm_speed = fan_data.get("speed_rpm")
            percent_speed = fan_data.get("speed_percent")
            fan_name = fan_data.get("name", fan_id)
            
            if rpm_speed is not None and rpm_speed > 0:
                fan_speeds.append(rpm_speed)
                fan_names.append(f"{fan_name} ({rpm_speed} RPM)")
                rpm_count += 1
            elif percent_speed is not None and percent_speed > 0:
                estimated_rpm = (percent_speed / 100) * 3000
                fan_speeds.append(estimated_rpm)
                fan_names.append(f"{fan_name} ({percent_speed}% ≈{int(estimated_rpm)} RPM)")
                percent_count += 1
        
        if not fan_speeds:
            return None
            
        return {
            "fan_count": len(fan_speeds),
            "min_speed": round(min(fan_speeds)),
            "max_speed": round(max(fan_speeds)),
            "rpm_sensors": rpm_count,
            "percent_sensors": percent_count,
            "fans": fan_names,
        }


class IdracTemperatureDeltaSensor(IdracSensor):
    """Airflow thermal efficiency showing temperature rise from inlet to outlet."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "temperature_delta", "Temperature Rise")
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None  # Primary thermal measurement
        self._attr_icon = "mdi:thermometer-lines"

    @property
    def native_value(self) -> float | None:
        """Return the temperature delta between inlet and outlet."""
        if not self.coordinator.data or "temperatures" not in self.coordinator.data:
            return None
        
        temperatures = self.coordinator.data["temperatures"]
        inlet_temp = None
        outlet_temp = None
        
        # Find inlet and outlet temperature sensors
        for temp_id, temp_data in temperatures.items():
            temp_name = temp_data.get("name", "").lower()
            temp_value = temp_data.get("temperature")
            
            if temp_value is not None:
                if any(keyword in temp_name for keyword in ["inlet", "intake", "ambient"]):
                    inlet_temp = temp_value
                elif any(keyword in temp_name for keyword in ["outlet", "exhaust", "exit"]):
                    outlet_temp = temp_value
        
        # Calculate delta if both temperatures are available
        if inlet_temp is not None and outlet_temp is not None:
            return round(outlet_temp - inlet_temp, 1)
        
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about the temperature delta."""
        if not self.coordinator.data or "temperatures" not in self.coordinator.data:
            return None
        
        temperatures = self.coordinator.data["temperatures"]
        inlet_temp = None
        outlet_temp = None
        inlet_sensor = None
        outlet_sensor = None
        
        # Find inlet and outlet temperature sensors
        for temp_id, temp_data in temperatures.items():
            temp_name = temp_data.get("name", "").lower()
            temp_value = temp_data.get("temperature")
            
            if temp_value is not None:
                if any(keyword in temp_name for keyword in ["inlet", "intake", "ambient"]):
                    inlet_temp = temp_value
                    inlet_sensor = temp_data.get("name", temp_id)
                elif any(keyword in temp_name for keyword in ["outlet", "exhaust", "exit"]):
                    outlet_temp = temp_value  
                    outlet_sensor = temp_data.get("name", temp_id)
        
        if inlet_temp is not None or outlet_temp is not None:
            return {
                "inlet_temperature": inlet_temp,
                "outlet_temperature": outlet_temp,
                "inlet_sensor": inlet_sensor,
                "outlet_sensor": outlet_sensor,
                "delta_available": inlet_temp is not None and outlet_temp is not None,
            }
        
        return None


class IdracProcessorModelSensor(IdracSensor):
    """Processor model sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor model sensor."""
        super().__init__(coordinator, config_entry, "processor_model", "CPU Model")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_model")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_model") is not None


class IdracMemoryMirroringSensor(IdracSensor):
    """Memory mirroring configuration sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the memory mirroring sensor."""
        super().__init__(coordinator, config_entry, "memory_mirroring", "Memory Mirroring")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:content-duplicate"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_mirroring")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_mirroring") is not None


class IdracProcessorStatusSensor(IdracSensor):
    """Processor status diagnostic sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor status sensor."""
        super().__init__(coordinator, config_entry, "processor_status", "Processor Status")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:chip"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_status")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_status") is not None


class IdracMemoryStatusSensor(IdracSensor):
    """Memory status diagnostic sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the memory status sensor."""
        super().__init__(coordinator, config_entry, "memory_status", "Memory Status")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:memory"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_status")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_status") is not None


class IdracMemoryTypeSensor(IdracSensor):
    """Memory type configuration sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the memory type sensor."""
        super().__init__(coordinator, config_entry, "memory_type", "Memory Type")
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:memory-arrow-down"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_type")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_type") is not None


class IdracProcessorMaxSpeedSensor(IdracSensor):
    """Processor max speed configuration sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor max speed sensor."""
        super().__init__(coordinator, config_entry, "processor_max_speed", "Processor Max Speed")
        self._attr_native_unit_of_measurement = "MHz"
        self._attr_device_class = SensorDeviceClass.FREQUENCY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = None
        self._attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_max_speed_mhz")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        max_speed = system_info.get("processor_max_speed_mhz")
        
        # Debug logging to help diagnose availability issues
        if max_speed is None:
            _LOGGER.debug("Processor max speed unavailable - system_info keys: %s", 
                         list(system_info.keys()) if system_info else "No system_info")
        
        return max_speed is not None


class IdracProcessorCurrentSpeedSensor(IdracSensor):
    """Processor current speed sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor current speed sensor."""
        super().__init__(coordinator, config_entry, "processor_current_speed", "Processor Current Speed")
        self._attr_native_unit_of_measurement = "MHz"
        self._attr_device_class = SensorDeviceClass.FREQUENCY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        # No entity_category - appears in main sensors section
        self._attr_icon = "mdi:speedometer-medium"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_current_speed_mhz")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False
        system_info = self.coordinator.data.get("system_info", {})
        current_speed = system_info.get("processor_current_speed_mhz")
        
        # Debug logging to help diagnose availability issues
        if current_speed is None:
            _LOGGER.debug("Processor current speed unavailable - system_info keys: %s", 
                         list(system_info.keys()) if system_info else "No system_info")
        
        return current_speed is not None


