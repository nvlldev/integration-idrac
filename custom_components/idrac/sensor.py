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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, REDFISH_HEALTH_STATUS
from .coordinator_snmp import SNMPDataUpdateCoordinator
from .coordinator_redfish import RedfishDataUpdateCoordinator
from .utils import get_device_name_prefix

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC sensors."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    snmp_coordinator = coordinators["snmp"]
    redfish_coordinator = coordinators["redfish"]
    
    entities: list[IdracSensor] = []
    
    # Log sensor setup progress
    snmp_categories = []
    redfish_categories = []
    
    _LOGGER.debug("SNMP coordinator: %s, last_update_success: %s, data keys: %s", 
                  snmp_coordinator, snmp_coordinator.last_update_success if snmp_coordinator else None,
                  list(snmp_coordinator.data.keys()) if snmp_coordinator and snmp_coordinator.data else "None")
    _LOGGER.debug("Redfish coordinator: %s, last_update_success: %s, data keys: %s", 
                  redfish_coordinator, redfish_coordinator.last_update_success if redfish_coordinator else None,
                  list(redfish_coordinator.data.keys()) if redfish_coordinator and redfish_coordinator.data else "None")
    
    if snmp_coordinator and snmp_coordinator.data:
        snmp_categories = [k for k, v in snmp_coordinator.data.items() if v]
        _LOGGER.info("SNMP coordinator has %d data categories: %s", 
                     len(snmp_categories), ", ".join(snmp_categories))
    else:
        _LOGGER.warning("SNMP coordinator has no data available")
    
    if redfish_coordinator and redfish_coordinator.data:
        redfish_categories = [k for k, v in redfish_coordinator.data.items() if v]
        _LOGGER.info("Redfish coordinator has %d data categories: %s", 
                     len(redfish_categories), ", ".join(redfish_categories))
    else:
        _LOGGER.warning("Redfish coordinator has no data available")
    
    def get_coordinator_for_category(category: str):
        """Determine which coordinator to use for a given data category."""
        _LOGGER.debug("Looking for coordinator for category: %s", category)
        
        # SNMP categories (typically faster, more frequent updates)
        snmp_categories_list = [
            "temperatures", "fans", "power_supplies", "voltages", "memory",
            "virtual_disks", "physical_disks", "storage_controllers", 
            "system_voltages", "power_consumption", "intrusion_detection",
            "battery", "processors"
        ]
        
        # Redfish categories (system controls and some sensors)
        redfish_categories_list = [
            "system_info", "manager_info", "chassis_info", "power_redundancy",
            "system_health", "indicator_led_state", "chassis_intrusion"
        ]
        
        # Check which coordinator actually has data for this category
        if category in snmp_categories_list:
            if snmp_coordinator and snmp_coordinator.data and category in snmp_coordinator.data and snmp_coordinator.data[category]:
                _LOGGER.debug("Using SNMP coordinator for %s", category)
                return snmp_coordinator
        
        if category in redfish_categories_list:
            if redfish_coordinator and redfish_coordinator.data and category in redfish_coordinator.data and redfish_coordinator.data[category]:
                _LOGGER.debug("Using Redfish coordinator for %s", category)
                return redfish_coordinator
                
        # Fallback: use whichever coordinator has the data
        if snmp_coordinator and snmp_coordinator.data and category in snmp_coordinator.data and snmp_coordinator.data[category]:
            _LOGGER.debug("Using SNMP coordinator for %s (fallback)", category)
            return snmp_coordinator
        elif redfish_coordinator and redfish_coordinator.data and category in redfish_coordinator.data and redfish_coordinator.data[category]:
            _LOGGER.debug("Using Redfish coordinator for %s (fallback)", category)
            return redfish_coordinator
        
        _LOGGER.debug("No coordinator found for category: %s", category)
        return None

    # Add power consumption sensor
    power_coordinator = get_coordinator_for_category("power_consumption")
    if power_coordinator and power_coordinator.data and "power_consumption" in power_coordinator.data:
        entities.append(IdracPowerConsumptionSensor(power_coordinator, config_entry))
        _LOGGER.debug("Power consumption sensor using %s coordinator", "SNMP" if power_coordinator == snmp_coordinator else "Redfish")

    # Add temperature sensors
    temp_coordinator = get_coordinator_for_category("temperatures")
    if temp_coordinator and temp_coordinator.data and "temperatures" in temp_coordinator.data:
        temp_count = len(temp_coordinator.data["temperatures"])
        if temp_count > 0:
            _LOGGER.info("Creating %d temperature sensors using %s coordinator", temp_count, "SNMP" if temp_coordinator == snmp_coordinator else "Redfish")
            for temp_id, temp_data in temp_coordinator.data["temperatures"].items():
                entities.append(IdracTemperatureSensor(temp_coordinator, config_entry, temp_id, temp_data))
        else:
            _LOGGER.warning("Temperature data category exists but contains no sensors")

    # Add fan sensors  
    fan_coordinator = get_coordinator_for_category("fans")
    if fan_coordinator and fan_coordinator.data and "fans" in fan_coordinator.data:
        fan_count = len(fan_coordinator.data["fans"])
        if fan_count > 0:
            _LOGGER.info("Creating %d fan sensors using %s coordinator", fan_count, "SNMP" if fan_coordinator == snmp_coordinator else "Redfish") 
            for fan_id, fan_data in fan_coordinator.data["fans"].items():
                entities.append(IdracFanSpeedSensor(fan_coordinator, config_entry, fan_id, fan_data))
        else:
            _LOGGER.warning("Fan data category exists but contains no sensors")

    # Define sensor mappings for automated creation
    # Format: (category, sensor_type, sensor_class, takes_item_params)
    sensor_mappings = [
        ("voltages", "voltage", IdracVoltageSensor, True),
        ("intrusion_detection", "intrusion", IdracIntrusionSensor, True),
        ("battery", "battery", IdracBatterySensor, True),
        ("processors", "processor", IdracProcessorSensor, True),
    ]
    
    # Create sensors for each category
    for category, sensor_type, sensor_class, takes_item_params in sensor_mappings:
        coordinator = get_coordinator_for_category(category)
        if coordinator and coordinator.data and category in coordinator.data:
            items = coordinator.data[category]
            if items:
                _LOGGER.info("Creating %d %s sensors using %s coordinator", 
                            len(items), sensor_type, "SNMP" if coordinator == snmp_coordinator else "Redfish")
                for item_id, item_data in items.items():
                    if takes_item_params:
                        entities.append(sensor_class(coordinator, config_entry, item_id, item_data))
                    else:
                        entities.append(sensor_class(coordinator, config_entry))
    
    # Add special memory sensor (doesn't take item parameters)
    memory_coordinator = get_coordinator_for_category("memory")
    if memory_coordinator and memory_coordinator.data and "memory" in memory_coordinator.data and memory_coordinator.data["memory"]:
        entities.append(IdracMemorySensor(memory_coordinator, config_entry))
        _LOGGER.info("Creating memory total sensor using %s coordinator", "SNMP" if memory_coordinator == snmp_coordinator else "Redfish")

    # Add memory health sensors (additional sensors using the same memory data)
    memory_coordinator = get_coordinator_for_category("memory")
    if memory_coordinator and memory_coordinator.data and "memory" in memory_coordinator.data:
        for memory_id, memory_data in memory_coordinator.data["memory"].items():
            entities.append(IdracMemoryHealthSensor(memory_coordinator, config_entry, memory_id, memory_data))

    # Add system info sensors (typically from Redfish)
    system_coordinator = get_coordinator_for_category("system_info")
    if system_coordinator and system_coordinator.data and "system_info" in system_coordinator.data:
        system_info = system_coordinator.data["system_info"]
        _LOGGER.info("System info available for sensor creation using %s coordinator: %s", 
                    "SNMP" if system_coordinator == snmp_coordinator else "Redfish", system_info)
        
        # Debug each field individually
        memory_gb = system_info.get("memory_gb")
        processor_count = system_info.get("processor_count") 
        processor_model = system_info.get("processor_model")
        
        _LOGGER.info("System info fields - memory_gb: %s, processor_count: %s, processor_model: %s", 
                    memory_gb, processor_count, processor_model)
        
        if memory_gb:
            _LOGGER.info("Creating IdracMemorySensor")
            entities.append(IdracMemorySensor(system_coordinator, config_entry))
        else:
            _LOGGER.warning("Memory GB not available: %s", memory_gb)
            
        if processor_count:
            _LOGGER.info("Creating IdracProcessorCountSensor") 
            entities.append(IdracProcessorCountSensor(system_coordinator, config_entry))
        else:
            _LOGGER.warning("Processor count not available: %s", processor_count)
            
        if processor_model:
            _LOGGER.info("Creating IdracProcessorModelSensor")
            entities.append(IdracProcessorModelSensor(system_coordinator, config_entry))
        else:
            _LOGGER.warning("Processor model not available: %s", processor_model)
        # Debug the new sensors we added
        memory_mirroring = system_info.get("memory_mirroring")
        memory_type = system_info.get("memory_type")
        processor_status = system_info.get("processor_status")
        memory_status = system_info.get("memory_status")
        processor_max_speed = system_info.get("processor_max_speed_mhz")
        processor_current_speed = system_info.get("processor_current_speed_mhz")
        
        _LOGGER.info("New sensor fields - memory_mirroring: %s, memory_type: %s, processor_status: %s, memory_status: %s, processor_max_speed: %s, processor_current_speed: %s",
                    memory_mirroring, memory_type, processor_status, memory_status, processor_max_speed, processor_current_speed)
        
        if memory_mirroring:
            _LOGGER.info("Creating IdracMemoryMirroringSensor")
            entities.append(IdracMemoryMirroringSensor(system_coordinator, config_entry))
        if memory_type:
            _LOGGER.info("Creating IdracMemoryTypeSensor")
            entities.append(IdracMemoryTypeSensor(system_coordinator, config_entry))
        if processor_status:
            _LOGGER.info("Creating IdracProcessorStatusSensor")
            entities.append(IdracProcessorStatusSensor(system_coordinator, config_entry))
        if memory_status:
            _LOGGER.info("Creating IdracMemoryStatusSensor")
            entities.append(IdracMemoryStatusSensor(system_coordinator, config_entry))
        if processor_max_speed:
            _LOGGER.info("Creating IdracProcessorMaxSpeedSensor")
            entities.append(IdracProcessorMaxSpeedSensor(system_coordinator, config_entry))
        if processor_current_speed:
            _LOGGER.info("Creating IdracProcessorCurrentSpeedSensor")
            entities.append(IdracProcessorCurrentSpeedSensor(system_coordinator, config_entry))
        # Note: Power state, chassis intrusion, power redundancy, and system health 
        # are handled by binary sensors - no duplicate regular sensors needed

    # Add manager info sensors (Redfish only)
    manager_coordinator = get_coordinator_for_category("manager_info")
    if manager_coordinator and manager_coordinator.data and "manager_info" in manager_coordinator.data:
        manager_info = manager_coordinator.data["manager_info"]
        if manager_info.get("firmware_version"):
            entities.append(IdracFirmwareVersionSensor(manager_coordinator, config_entry))
        if manager_info.get("datetime"):
            entities.append(IdracDateTimeSensor(manager_coordinator, config_entry))

    # Add additional PSU power sensors for Redfish
    psu_coordinator = get_coordinator_for_category("power_supplies")
    if psu_coordinator and psu_coordinator.data and "power_supplies" in psu_coordinator.data:
        for psu_id, psu_data in psu_coordinator.data["power_supplies"].items():
            # PSU input power sensor removed as requested
            # Output power sensor
            if psu_data.get("power_output_watts") is not None:
                entities.append(IdracPSUOutputPowerSensor(psu_coordinator, config_entry, psu_id, psu_data))
            # Input voltage sensor
            if psu_data.get("line_input_voltage") is not None:
                entities.append(IdracPSUInputVoltageSensor(psu_coordinator, config_entry, psu_id, psu_data))

    # Add advanced power metrics (Redfish only)
    power_consumption_coordinator = get_coordinator_for_category("power_consumption")
    if power_consumption_coordinator and power_consumption_coordinator.data and "power_consumption" in power_consumption_coordinator.data:
        power_data = power_consumption_coordinator.data["power_consumption"]
        if power_data.get("average_consumed_watts") is not None:
            entities.append(IdracAveragePowerSensor(power_consumption_coordinator, config_entry))
        if power_data.get("max_consumed_watts") is not None:
            entities.append(IdracMaxPowerSensor(power_consumption_coordinator, config_entry))
        if power_data.get("min_consumed_watts") is not None:
            entities.append(IdracMinPowerSensor(power_consumption_coordinator, config_entry))

    # Add performance and analytical sensors 
    # Note: These sensors will use whichever coordinator has the relevant data
    
    # Average CPU temperature sensor - available when CPU temperature sensors exist
    temp_coordinator = get_coordinator_for_category("temperatures")
    if temp_coordinator and temp_coordinator.data and "temperatures" in temp_coordinator.data:
        temp_data = temp_coordinator.data["temperatures"]
        cpu_temp_count = sum(1 for temp_item in temp_data.values() 
                           if any(keyword in temp_item.get("name", "").lower() 
                                for keyword in ["cpu", "processor", "proc"]))
        if cpu_temp_count > 0:
            entities.append(IdracAverageCpuTemperatureSensor(temp_coordinator, config_entry))
    
    # Average fan speed sensor - available when fan sensors exist  
    fan_coordinator = get_coordinator_for_category("fans")
    if fan_coordinator and fan_coordinator.data and "fans" in fan_coordinator.data and fan_coordinator.data["fans"]:
        entities.append(IdracAverageFanSpeedSensor(fan_coordinator, config_entry))
            
    # Temperature delta sensor - available when inlet/outlet sensors exist
    if temp_coordinator and temp_coordinator.data and "temperatures" in temp_coordinator.data:
        temp_data = temp_coordinator.data["temperatures"]
        has_inlet = any(any(keyword in temp_item.get("name", "").lower() 
                          for keyword in ["inlet", "intake", "ambient"])
                      for temp_item in temp_data.values())
        has_outlet = any(any(keyword in temp_item.get("name", "").lower() 
                           for keyword in ["outlet", "exhaust", "exit"])
                       for temp_item in temp_data.values())
        if has_inlet or has_outlet:  # Show sensor even if only one is available
            entities.append(IdracTemperatureDeltaSensor(temp_coordinator, config_entry))

    if entities:
        _LOGGER.info("Successfully created %d sensor entities for iDRAC", len(entities))
    else:
        _LOGGER.error("No sensor entities created - check SNMP/Redfish connectivity and sensor discovery")
    
    async_add_entities(entities)




class IdracSensor(CoordinatorEntity[SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator], SensorEntity):
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
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self.config_entry = config_entry
        host = coordinator.host
        
        # Include device prefix in name for proper entity_id generation
        device_prefix = get_device_name_prefix(coordinator)
        self._attr_name = f"{device_prefix} {sensor_name}"
        # Use stable unique_id based on host and sensor key (like original)
        self._attr_unique_id = f"{host}_{sensor_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if unit:  # Only set state class if we have a unit
            self._attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Set device info now that we can make async calls
        try:
            self._attr_device_info = await self.coordinator.get_device_info()
        except Exception as exc:
            _LOGGER.warning("Failed to get device info for sensor: %s", exc)
            # Provide fallback device info to ensure device is created
            self._attr_device_info = {
                "identifiers": {("idrac", self.coordinator.host)},
                "name": f"Dell iDRAC ({self.coordinator.host})",
                "manufacturer": "Dell",
                "model": "iDRAC",
                "configuration_url": f"https://{self.coordinator.host}",
            }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)

    @property
    def device_info(self):
        """Return device information."""
        # Always return device info - use fallback if not set
        if hasattr(self, '_attr_device_info') and self._attr_device_info:
            return self._attr_device_info
        
        # Fallback device info
        return {
            "identifiers": {("idrac", self.coordinator.host)},
            "name": f"Dell iDRAC ({self.coordinator.host})",
            "manufacturer": "Dell", 
            "model": "iDRAC",
            "configuration_url": f"https://{self.coordinator.host}",
        }

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



class IdracMemoryHealthSensor(IdracSensor):
    """Memory health sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        memory_id: str,
        memory_data: dict[str, Any],
    ) -> None:
        """Initialize the memory health sensor."""
        memory_name = memory_data.get("name", f"Memory {memory_id}")
        super().__init__(coordinator, config_entry, f"memory_{memory_id}_health", f"{memory_name} Health")
        self.memory_id = memory_id
        self._attr_entity_category = None

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "memory" not in self.coordinator.data:
            return None
        memory_data = self.coordinator.data["memory"].get(self.memory_id)
        if not memory_data:
            return None
        return memory_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "ok":
            return "mdi:memory"
        elif status in ["non_critical", "critical", "non_recoverable"]:
            return "mdi:memory-alert"
        else:
            return "mdi:memory-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data or "memory" not in self.coordinator.data:
            return None
        memory_data = self.coordinator.data["memory"].get(self.memory_id)
        if not memory_data:
            return None
        return {
            "size_kb": memory_data.get("size_kb"),
            "name": memory_data.get("name"),
        }


# PSU status sensors are handled by binary sensors - regular PSU status sensor class removed


class IdracIntrusionSensor(IdracSensor):
    """Chassis intrusion sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        intrusion_id: str,
        intrusion_data: dict[str, Any],
    ) -> None:
        """Initialize the chassis intrusion sensor."""
        intrusion_name = intrusion_data.get("name", f"Intrusion {intrusion_id}")
        super().__init__(coordinator, config_entry, f"intrusion_{intrusion_id}", f"{intrusion_name} Detection")
        self.intrusion_id = intrusion_id
        self._attr_entity_category = None

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "intrusion_detection" not in self.coordinator.data:
            return None
        intrusion_data = self.coordinator.data["intrusion_detection"].get(self.intrusion_id)
        if not intrusion_data:
            return None
        return intrusion_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "ok":
            return "mdi:shield-check"
        elif status == "breach":
            return "mdi:shield-alert"
        else:
            return "mdi:shield-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data or "intrusion_detection" not in self.coordinator.data:
            return None
        intrusion_data = self.coordinator.data["intrusion_detection"].get(self.intrusion_id)
        if not intrusion_data:
            return None
        return {
            "reading": intrusion_data.get("reading"),
            "name": intrusion_data.get("name"),
        }


class IdracBatterySensor(IdracSensor):
    """System battery sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        battery_id: str,
        battery_data: dict[str, Any],
    ) -> None:
        """Initialize the battery sensor."""
        battery_name = battery_data.get("name", f"Battery {battery_id}")
        super().__init__(coordinator, config_entry, f"battery_{battery_id}", f"{battery_name} Health")
        self.battery_id = battery_id
        self._attr_entity_category = None

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data or "battery" not in self.coordinator.data:
            return None
        battery_data = self.coordinator.data["battery"].get(self.battery_id)
        if not battery_data:
            return None
        return battery_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "ok":
            return "mdi:battery"
        elif status in ["non_critical", "critical", "non_recoverable"]:
            return "mdi:battery-alert"
        else:
            return "mdi:battery-unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data or "battery" not in self.coordinator.data:
            return None
        battery_data = self.coordinator.data["battery"].get(self.battery_id)
        if not battery_data:
            return None
        return {
            "reading": battery_data.get("reading"),
            "name": battery_data.get("name"),
        }


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


class IdracPSUOutputPowerSensor(IdracSensor):
    """PSU output power sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry, 
                 psu_id: str, psu_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        psu_index = psu_id.replace('psu_', '') if psu_id.startswith('psu_') else psu_id
        super().__init__(coordinator, config_entry, f"{psu_id}_output_power", f"Power Supply {psu_index} Output Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash-outline"
        self.psu_id = psu_id

    @property
    def native_value(self) -> float | None:
        """Return the PSU output power."""
        if not self.coordinator.data or "power_supplies" not in self.coordinator.data:
            return None
        psu_data = self.coordinator.data["power_supplies"].get(self.psu_id)
        if not psu_data:
            return None
        return psu_data.get("power_output_watts")


class IdracPSUInputVoltageSensor(IdracSensor):
    """PSU input voltage sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry, 
                 psu_id: str, psu_data: dict[str, Any]) -> None:
        """Initialize the sensor."""
        psu_index = psu_id.replace('psu_', '') if psu_id.startswith('psu_') else psu_id
        super().__init__(coordinator, config_entry, f"{psu_id}_input_voltage", f"Power Supply {psu_index} Input Voltage")
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_icon = "mdi:lightning-bolt"
        self.psu_id = psu_id

    @property
    def native_value(self) -> float | None:
        """Return the PSU input voltage."""
        if not self.coordinator.data or "power_supplies" not in self.coordinator.data:
            return None
        psu_data = self.coordinator.data["power_supplies"].get(self.psu_id)
        if not psu_data:
            return None
        return psu_data.get("line_input_voltage")


class IdracAveragePowerSensor(IdracSensor):
    """System average power consumption sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "average_power_consumption", "System Average Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash-outline"

    @property
    def native_value(self) -> float | None:
        """Return the average power consumption."""
        if not self.coordinator.data or "power_consumption" not in self.coordinator.data:
            return None
        return self.coordinator.data["power_consumption"].get("average_consumed_watts")


class IdracMaxPowerSensor(IdracSensor):
    """System maximum power consumption sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "max_power_consumption", "System Peak Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash-triangle"

    @property
    def native_value(self) -> float | None:
        """Return the maximum power consumption."""
        if not self.coordinator.data or "power_consumption" not in self.coordinator.data:
            return None
        return self.coordinator.data["power_consumption"].get("max_consumed_watts")


class IdracMinPowerSensor(IdracSensor):
    """System minimum power consumption sensor."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "min_power_consumption", "System Minimum Power")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_icon = "mdi:flash-off"

    @property
    def native_value(self) -> float | None:
        """Return the minimum power consumption."""
        if not self.coordinator.data or "power_consumption" not in self.coordinator.data:
            return None
        return self.coordinator.data["power_consumption"].get("min_consumed_watts")


class IdracUpdateLatencySensor(IdracSensor):
    """Response time sensor showing how long it takes to collect all sensor data."""
    
    def __init__(self, coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, "update_latency", "Update Response Time")
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "s"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:timer-outline"

    @property
    def native_value(self) -> float | None:
        """Return the data collection time in seconds."""
        if not self.coordinator.data or "update_latency" not in self.coordinator.data:
            return None
        return self.coordinator.data["update_latency"].get("collection_time_seconds")
    
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes about the data collection."""
        if not self.coordinator.data or "update_latency" not in self.coordinator.data:
            return None
        
        latency_data = self.coordinator.data["update_latency"]
        return {
            "redfish_sensors": latency_data.get("redfish_sensor_count", 0),
            "snmp_sensors": latency_data.get("snmp_sensor_count", 0), 
            "total_sensors": latency_data.get("total_sensor_count", 0),
            "collection_method": "concurrent",
        }


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
        self._attr_entity_category = None
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
        self._attr_entity_category = None
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
        return system_info.get("processor_max_speed_mhz") is not None


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
        return system_info.get("processor_current_speed_mhz") is not None


