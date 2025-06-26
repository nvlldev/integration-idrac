"""Sensor platform for Dell iDRAC integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DISCOVERED_CPUS, CONF_DISCOVERED_FANS, CONF_DISCOVERED_PSUS, CONF_DISCOVERED_VOLTAGE_PROBES, DOMAIN
from .coordinator import IdracDataUpdateCoordinator


def _to_snake_case(text: str) -> str:
    """Convert text to snake_case for entity ID compatibility."""
    import re
    # Replace spaces and special characters with underscores
    snake = re.sub(r'[^a-zA-Z0-9]', '_', text.lower())
    # Remove multiple underscores
    snake = re.sub(r'_+', '_', snake)
    # Remove leading/trailing underscores
    return snake.strip('_')


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC sensors."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracSensor] = [
        IdracPowerSensor(coordinator, config_entry),
        IdracTemperatureSensor(coordinator, config_entry, "temp_inlet", "Inlet Temperature"),
        IdracTemperatureSensor(coordinator, config_entry, "temp_outlet", "Outlet Temperature"),
    ]

    # Add CPU temperature sensors
    for cpu_index in config_entry.data.get(CONF_DISCOVERED_CPUS, []):
        entities.append(
            IdracCpuTemperatureSensor(coordinator, config_entry, cpu_index)
        )

    # Add fan speed sensors
    for fan_index in config_entry.data.get(CONF_DISCOVERED_FANS, []):
        entities.append(
            IdracFanSensor(coordinator, config_entry, fan_index)
        )

    # Add PSU amperage sensors
    for psu_index in config_entry.data.get(CONF_DISCOVERED_PSUS, []):
        entities.append(
            IdracPsuAmperageSensor(coordinator, config_entry, psu_index)
        )

    # Add PSU voltage sensors (discovered separately)
    voltage_probes = config_entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])
    for i, voltage_probe_index in enumerate(voltage_probes, 1):
        entities.append(
            IdracPsuVoltageSensor(coordinator, config_entry, voltage_probe_index, i)
        )

    async_add_entities(entities)


class IdracSensor(CoordinatorEntity, SensorEntity):
    """Base class for Dell iDRAC sensors."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        self._attr_name = sensor_name
        # Use device name with host prefix for auto-rename compatibility
        host_snake = _to_snake_case(host)
        descriptive_key = sensor_key.replace("temp_", "temperature_")
        self._attr_unique_id = f"dell_idrac_{host_snake}_{descriptive_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{host}",
        }

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.native_value is not None


class IdracPowerSensor(IdracSensor):
    """Dell iDRAC power sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "power",
            "Power Consumption",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        )


class IdracTemperatureSensor(IdracSensor):
    """Dell iDRAC temperature sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
    ) -> None:
        """Initialize the temperature sensor."""
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        )


class IdracCpuTemperatureSensor(IdracSensor):
    """Dell iDRAC CPU temperature sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        cpu_index: int,
    ) -> None:
        """Initialize the CPU temperature sensor."""
        sensor_key = f"cpu_{cpu_index}"
        sensor_name = f"CPU {cpu_index - 2} Temperature"
    
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        )
        # Override the unique_id for auto-rename compatibility
        host = config_entry.data[CONF_HOST]
        host_snake = _to_snake_case(host)
        self._attr_unique_id = f"dell_idrac_{host_snake}_cpu_{cpu_index - 2}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None or "cpu_temps" not in self.coordinator.data:
            return None
        return self.coordinator.data["cpu_temps"].get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "cpu_temps" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["cpu_temps"]
            and self.coordinator.data["cpu_temps"][self._sensor_key] is not None
        )


class IdracFanSensor(IdracSensor):
    """Dell iDRAC fan sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        fan_index: int,
    ) -> None:
        """Initialize the fan sensor."""
        sensor_key = f"fan_{fan_index}"
        sensor_name = f"Fan {fan_index} Speed"
        
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            REVOLUTIONS_PER_MINUTE,
        )
        # Override the unique_id for auto-rename compatibility
        host = config_entry.data[CONF_HOST]
        host_snake = _to_snake_case(host)
        self._attr_unique_id = f"dell_idrac_{host_snake}_fan_{fan_index}_speed"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None or "fans" not in self.coordinator.data:
            return None
        return self.coordinator.data["fans"].get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "fans" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["fans"]
            and self.coordinator.data["fans"][self._sensor_key] is not None
        )


class IdracPsuVoltageSensor(IdracSensor):
    """Dell iDRAC PSU voltage sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        voltage_probe_index: int,
        psu_number: int = None,
    ) -> None:
        """Initialize the PSU voltage sensor."""
        sensor_key = f"psu_voltage_{voltage_probe_index}"
        # Use sequential PSU numbering if provided, otherwise use probe index
        display_number = psu_number if psu_number is not None else voltage_probe_index
        sensor_name = f"PSU {display_number} Voltage"
        
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            UnitOfElectricPotential.VOLT,
            SensorDeviceClass.VOLTAGE,
        )
        # Override the unique_id for auto-rename compatibility
        host = config_entry.data[CONF_HOST]
        host_snake = _to_snake_case(host)
        self._attr_unique_id = f"dell_idrac_{host_snake}_psu_{display_number}_voltage"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None or "psu_voltages" not in self.coordinator.data:
            return None
        return self.coordinator.data["psu_voltages"].get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "psu_voltages" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["psu_voltages"]
            and self.coordinator.data["psu_voltages"][self._sensor_key] is not None
        )




class IdracPsuAmperageSensor(IdracSensor):
    """Dell iDRAC PSU amperage sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        psu_index: int,
    ) -> None:
        """Initialize the PSU amperage sensor."""
        sensor_key = f"psu_amperage_{psu_index}"
        sensor_name = f"PSU {psu_index} Amperage"
        
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            UnitOfElectricCurrent.AMPERE,
            SensorDeviceClass.CURRENT,
        )
        # Override the unique_id for auto-rename compatibility
        host = config_entry.data[CONF_HOST]
        host_snake = _to_snake_case(host)
        self._attr_unique_id = f"dell_idrac_{host_snake}_psu_{psu_index}_amperage"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None or "psu_amperages" not in self.coordinator.data:
            return None
        return self.coordinator.data["psu_amperages"].get(self._sensor_key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "psu_amperages" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["psu_amperages"]
            and self.coordinator.data["psu_amperages"][self._sensor_key] is not None
        )