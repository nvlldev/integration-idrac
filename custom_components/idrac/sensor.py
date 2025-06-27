"""Sensor platform for Dell iDRAC integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
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
from .coordinator import IdracDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC sensors."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracSensor] = []

    # Add power consumption sensor
    if coordinator.data and "power_consumption" in coordinator.data:
        entities.append(IdracPowerConsumptionSensor(coordinator, config_entry))

    # Add temperature sensors
    if coordinator.data and "temperatures" in coordinator.data:
        for temp_id, temp_data in coordinator.data["temperatures"].items():
            entities.append(IdracTemperatureSensor(coordinator, config_entry, temp_id, temp_data))

    # Add fan sensors  
    if coordinator.data and "fans" in coordinator.data:
        for fan_id, fan_data in coordinator.data["fans"].items():
            entities.append(IdracFanSensor(coordinator, config_entry, fan_id, fan_data))

    # Add voltage sensors (filter out status sensors that show ~1v)
    if coordinator.data and "voltages" in coordinator.data:
        for voltage_id, voltage_data in coordinator.data["voltages"].items():
            voltage_reading = voltage_data.get("reading_volts")
            # Only create voltage sensors for actual voltage readings (not status indicators)
            # Skip if reading is exactly 1.0 or close to 1.0 (likely a status indicator)
            if voltage_reading is not None and (voltage_reading < 0.9 or voltage_reading > 1.1):
                entities.append(IdracVoltageSensor(coordinator, config_entry, voltage_id, voltage_data))

    # Add system info sensors
    if coordinator.data and "system_info" in coordinator.data:
        system_info = coordinator.data["system_info"]
        if system_info.get("memory_gb"):
            entities.append(IdracMemorySensor(coordinator, config_entry))
        if system_info.get("processor_count"):
            entities.append(IdracProcessorCountSensor(coordinator, config_entry))
        # Add power state sensor
        entities.append(IdracPowerStateSensor(coordinator, config_entry))

    # Add chassis intrusion sensor (Redfish only)
    if coordinator.connection_type == "redfish" and coordinator.data and "chassis_intrusion" in coordinator.data:
        entities.append(IdracChassisIntrusionSensor(coordinator, config_entry))

    # Add power redundancy sensor (Redfish only)
    if coordinator.connection_type == "redfish" and coordinator.data and "power_redundancy" in coordinator.data:
        entities.append(IdracPowerRedundancySensor(coordinator, config_entry))

    # Add system health sensor (Redfish only) 
    if coordinator.connection_type == "redfish" and coordinator.data and "system_health" in coordinator.data:
        entities.append(IdracSystemHealthSensor(coordinator, config_entry))

    async_add_entities(entities)


class IdracSensor(CoordinatorEntity[IdracDataUpdateCoordinator], SensorEntity):
    """Common base class for Dell iDRAC sensors."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"

    @property
    def device_info(self):
        """Return device information."""
        return self.coordinator.device_info


class IdracPowerConsumptionSensor(IdracSensor):
    """Power consumption sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power consumption sensor."""
        super().__init__(coordinator, config_entry, "power_consumption", "Power Consumption")
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        power_data = self.coordinator.data.get("power_consumption", {})
        return power_data.get("consumed_watts")

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
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
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        temp_id: str,
        temp_data: dict,
    ) -> None:
        """Initialize the temperature sensor."""
        name = temp_data.get("name", f"Temperature {temp_id}")
        super().__init__(coordinator, config_entry, f"temperature_{temp_id}", name)
        self.temp_id = temp_id
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        temp_data = self.coordinator.data.get("temperatures", {}).get(self.temp_id, {})
        return temp_data.get("temperature")

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        temp_data = self.coordinator.data.get("temperatures", {}).get(self.temp_id, {})
        return {
            "status": REDFISH_HEALTH_STATUS.get(temp_data.get("status")),
            "upper_threshold_critical": temp_data.get("upper_threshold_critical"),
            "upper_threshold_non_critical": temp_data.get("upper_threshold_non_critical"),
        }


class IdracFanSensor(IdracSensor):
    """Fan speed sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        fan_id: str,
        fan_data: dict,
    ) -> None:
        """Initialize the fan sensor."""
        name = fan_data.get("name", f"Fan {fan_id}")
        super().__init__(coordinator, config_entry, f"fan_{fan_id}", name)
        self.fan_id = fan_id
        self._attr_state_class = SensorStateClass.MEASUREMENT

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
    def extra_state_attributes(self) -> dict[str, any] | None:
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
        coordinator: IdracDataUpdateCoordinator,
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

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        voltage_data = self.coordinator.data.get("voltages", {}).get(self.voltage_id, {})
        return voltage_data.get("reading_volts")

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
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
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the memory sensor."""
        super().__init__(coordinator, config_entry, "memory_total", "Total Memory")
        self._attr_native_unit_of_measurement = "GB"
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("memory_gb")


class IdracProcessorCountSensor(IdracSensor):
    """Processor count sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the processor count sensor."""
        super().__init__(coordinator, config_entry, "processor_count", "Processor Count")
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("processor_count")

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return {
            "processor_model": system_info.get("processor_model"),
        }


class IdracPowerStateSensor(IdracSensor):
    """Power state sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power state sensor."""
        super().__init__(coordinator, config_entry, "power_state", "Power State")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("power_state", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        power_state = self.native_value
        if power_state == "On":
            return "mdi:power-on"
        elif power_state == "Off":
            return "mdi:power-off"
        else:
            return "mdi:power"


class IdracChassisIntrusionSensor(IdracSensor):
    """Chassis intrusion sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the chassis intrusion sensor."""
        super().__init__(coordinator, config_entry, "chassis_intrusion", "Chassis Intrusion")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        intrusion_data = self.coordinator.data.get("chassis_intrusion", {})
        return intrusion_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "Normal":
            return "mdi:shield-check"
        elif status in ["HardwareIntrusion", "TamperingDetected"]:
            return "mdi:shield-alert"
        else:
            return "mdi:shield"

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        intrusion_data = self.coordinator.data.get("chassis_intrusion", {})
        return {
            "sensor_number": intrusion_data.get("sensor_number"),
            "re_arm": intrusion_data.get("re_arm"),
        }


class IdracPowerRedundancySensor(IdracSensor):
    """Power supply redundancy sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power redundancy sensor."""
        super().__init__(coordinator, config_entry, "power_redundancy", "Power Redundancy")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        redundancy_data = self.coordinator.data.get("power_redundancy", {})
        return redundancy_data.get("status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "OK":
            return "mdi:power-plug"
        elif status == "Warning":
            return "mdi:power-plug-outline"
        elif status == "Critical":
            return "mdi:power-plug-off"
        else:
            return "mdi:power-socket"

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        redundancy_data = self.coordinator.data.get("power_redundancy", {})
        return {
            "mode": redundancy_data.get("mode"),
            "total_psus": redundancy_data.get("total_psus"),
            "healthy_psus": redundancy_data.get("healthy_psus"),
            "min_num_needed": redundancy_data.get("min_num_needed"),
            "max_num_supported": redundancy_data.get("max_num_supported"),
        }


class IdracSystemHealthSensor(IdracSensor):
    """Overall system health sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the system health sensor."""
        super().__init__(coordinator, config_entry, "system_health", "System Health")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        health_data = self.coordinator.data.get("system_health", {})
        return health_data.get("overall_status", "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        status = self.native_value
        if status == "OK":
            return "mdi:check-circle"
        elif status == "Warning":
            return "mdi:alert-circle"
        elif status == "Critical":
            return "mdi:alert-circle-outline"
        else:
            return "mdi:help-circle"

    @property
    def extra_state_attributes(self) -> dict[str, any] | None:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return None
        health_data = self.coordinator.data.get("system_health", {})
        return {
            "component_count": health_data.get("component_count"),
            "components": health_data.get("components"),
        }