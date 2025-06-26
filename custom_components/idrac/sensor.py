"""Sensor platform for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    UnitOfPower,
    UnitOfTemperature,
    REVOLUTIONS_PER_MINUTE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_DISCOVERED_FANS, CONF_DISCOVERED_CPUS
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

    entities.append(
        IdracPowerSensor(
            coordinator,
            config_entry,
            "power",
            "Power Consumption",
            UnitOfPower.WATT,
            SensorDeviceClass.POWER,
        )
    )

    temperature_sensors = [
        ("temp_inlet", "Inlet Temperature"),
        ("temp_outlet", "Outlet Temperature"),
    ]

    for sensor_key, sensor_name in temperature_sensors:
        entities.append(
            IdracTemperatureSensor(
                coordinator,
                config_entry,
                sensor_key,
                sensor_name,
            )
        )

    discovered_cpus = config_entry.data.get(CONF_DISCOVERED_CPUS, [])
    for cpu_index in discovered_cpus:
        entities.append(
            IdracCpuTemperatureSensor(
                coordinator,
                config_entry,
                f"cpu_{cpu_index}",
                f"CPU {cpu_index - 2} Temperature",
                cpu_index,
            )
        )

    discovered_fans = config_entry.data.get(CONF_DISCOVERED_FANS, [])
    for fan_index in discovered_fans:
        entities.append(
            IdracFanSensor(
                coordinator,
                config_entry,
                f"fan_{fan_index}",
                f"Fan {fan_index} Speed",
                fan_index,
            )
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
        self._attr_name = f"iDRAC {sensor_name}"
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Dell iDRAC ({config_entry.data[CONF_HOST]})",
            "manufacturer": "Dell",
            "model": "iDRAC",
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
        sensor_key: str,
        sensor_name: str,
        unit: str,
        device_class: SensorDeviceClass,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, config_entry, sensor_key, sensor_name, unit, device_class)


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
        sensor_key: str,
        sensor_name: str,
        cpu_index: int,
    ) -> None:
        """Initialize the CPU temperature sensor."""
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        )
        self._cpu_index = cpu_index

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
        )


class IdracFanSensor(IdracSensor):
    """Dell iDRAC fan sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
        fan_index: int,
    ) -> None:
        """Initialize the fan sensor."""
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            REVOLUTIONS_PER_MINUTE,
            None,
        )
        self._fan_index = fan_index

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
        )