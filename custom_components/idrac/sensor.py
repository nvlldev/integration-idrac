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
    CONF_HOST,
    CONF_PORT,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import CONF_DISCOVERED_CPUS, CONF_DISCOVERED_FANS, CONF_DISCOVERED_PSUS, CONF_DISCOVERED_VOLTAGE_PROBES, DOMAIN
from .coordinator import IdracDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_device_name_prefix(coordinator: IdracDataUpdateCoordinator) -> str:
    """Get device name prefix for entity naming."""
    device_info = coordinator.device_info
    if device_info and "model" in device_info and device_info["model"] != "iDRAC":
        return f"Dell {device_info['model']} ({coordinator.host})"
    else:
        return f"Dell iDRAC ({coordinator.host})"


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
        IdracTemperatureDeltaSensor(coordinator, config_entry, hass),
        IdracCpuSpeedSensor(coordinator, config_entry),
    ]

    # Add CPU temperature sensors
    cpu_indices = config_entry.data.get(CONF_DISCOVERED_CPUS, [])
    for cpu_index in cpu_indices:
        entities.append(
            IdracCpuTemperatureSensor(coordinator, config_entry, cpu_index)
        )
    
    # Add average CPU temperature sensor if multiple CPUs
    if len(cpu_indices) > 1:
        entities.append(
            IdracAverageCpuTemperatureSensor(coordinator, config_entry)
        )

    # Add fan speed sensors
    fan_indices = config_entry.data.get(CONF_DISCOVERED_FANS, [])
    for fan_index in fan_indices:
        entities.append(
            IdracFanSensor(coordinator, config_entry, fan_index)
        )
    
    # Add average fan speed sensor if multiple fans
    if len(fan_indices) > 1:
        entities.append(
            IdracAverageFanSpeedSensor(coordinator, config_entry)
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
        
        # Include device prefix in name for proper entity_id generation
        device_prefix = _get_device_name_prefix(coordinator)
        self._attr_name = f"{device_prefix} {sensor_name}"
        # Use stable unique_id based on device_id and sensor key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = coordinator.device_info

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


class IdracCpuSpeedSensor(IdracSensor):
    """Dell iDRAC CPU current speed sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the CPU speed sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "cpu_current_speed",
            "CPU Current Speed",
            UnitOfFrequency.MEGAHERTZ,
            SensorDeviceClass.FREQUENCY,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current CPU speed in MHz."""
        if self.coordinator.data is None:
            return None
        
        speed_mhz = self.coordinator.data.get("cpu_current_speed")
        if speed_mhz is not None and speed_mhz > 0:
            return speed_mhz
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return None
        
        speed_mhz = self.coordinator.data.get("cpu_current_speed")
        if speed_mhz is not None and speed_mhz > 0:
            # Convert to GHz for display
            speed_ghz = speed_mhz / 1000
            return {
                "speed_ghz": f"{speed_ghz:.2f} GHz",
                "speed_mhz": f"{speed_mhz} MHz"
            }
        return None


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


class IdracTemperatureDeltaSensor(IdracSensor):
    """Dell iDRAC temperature delta sensor (inlet - outlet)."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the temperature delta sensor."""
        self.hass = hass
        super().__init__(
            coordinator,
            config_entry,
            "temp_delta",
            "Airflow Temperature Rise",
            UnitOfTemperature.CELSIUS,
            None,  # No device class to avoid automatic temperature conversion
        )

    @property
    def native_value(self) -> float | None:
        """Return the temperature delta (outlet - inlet)."""
        if self.coordinator.data is None:
            return None
        
        outlet_temp = self.coordinator.data.get("temp_outlet")
        inlet_temp = self.coordinator.data.get("temp_inlet")
        
        if outlet_temp is not None and inlet_temp is not None:
            # Calculate delta in Celsius (raw data is in Celsius)
            delta_celsius = outlet_temp - inlet_temp
            
            # Check if user prefers Fahrenheit and convert delta accordingly
            # For temperature differences, we only apply the scaling factor (9/5), not the offset
            user_unit = self.hass.config.units.temperature_unit
            if user_unit == UnitOfTemperature.FAHRENHEIT:
                # Convert delta: 1°C difference = 1.8°F difference (no offset for deltas)
                delta = delta_celsius * 9/5
                self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            else:
                delta = delta_celsius
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            
            return round(delta, 1)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get("temp_outlet") is not None
            and self.coordinator.data.get("temp_inlet") is not None
        )


class IdracAverageCpuTemperatureSensor(IdracSensor):
    """Dell iDRAC average CPU temperature sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the average CPU temperature sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "cpu_temp_avg",
            "Average CPU Temperature",
            UnitOfTemperature.CELSIUS,
            SensorDeviceClass.TEMPERATURE,
        )

    @property
    def native_value(self) -> float | None:
        """Return the average CPU temperature."""
        if self.coordinator.data is None or "cpu_temps" not in self.coordinator.data:
            return None
        
        cpu_temps = [
            temp for temp in self.coordinator.data["cpu_temps"].values()
            if temp is not None and temp > 0
        ]
        
        if cpu_temps:
            return round(sum(cpu_temps) / len(cpu_temps), 1)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "cpu_temps" in self.coordinator.data
            and len([t for t in self.coordinator.data["cpu_temps"].values() if t is not None and t > 0]) > 0
        )


class IdracAverageFanSpeedSensor(IdracSensor):
    """Dell iDRAC average fan speed sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the average fan speed sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "fan_speed_avg",
            "Average Fan Speed",
            REVOLUTIONS_PER_MINUTE,
        )

    @property
    def native_value(self) -> float | None:
        """Return the average fan speed."""
        if self.coordinator.data is None or "fans" not in self.coordinator.data:
            return None
        
        fan_speeds = [
            speed for speed in self.coordinator.data["fans"].values()
            if speed is not None and speed > 0
        ]
        
        if fan_speeds:
            return round(sum(fan_speeds) / len(fan_speeds))
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "fans" in self.coordinator.data
            and len([s for s in self.coordinator.data["fans"].values() if s is not None and s > 0]) > 0
        )


class IdracVirtualDiskSensor(IdracSensor):
    """Dell iDRAC virtual disk sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        vdisk_index: int,
    ) -> None:
        """Initialize the virtual disk sensor."""
        sensor_key = f"vdisk_{vdisk_index}"
        sensor_name = f"Virtual Disk {vdisk_index}"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            None,
            SensorDeviceClass.ENUM,
        )
        self._vdisk_index = vdisk_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the virtual disk."""
        if self.coordinator.data is None or "virtual_disks" not in self.coordinator.data:
            return None
        
        vdisk_data = self.coordinator.data["virtual_disks"].get(self._sensor_key)
        if vdisk_data is None:
            return None
        
        state_value = vdisk_data.get("state")
        if state_value is not None:
            # Map Dell virtual disk states
            state_map = {
                1: "unknown",
                2: "online", 
                3: "degraded",
                4: "failed",
                6: "offline"
            }
            try:
                state_int = int(state_value)
                return state_map.get(state_int, f"unknown_{state_int}")
            except (ValueError, TypeError):
                return str(state_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "virtual_disks" not in self.coordinator.data:
            return None
        
        vdisk_data = self.coordinator.data["virtual_disks"].get(self._sensor_key)
        if vdisk_data is None:
            return None
        
        attributes = {}
        if vdisk_data.get("name"):
            attributes["name"] = str(vdisk_data["name"])
        if vdisk_data.get("size"):
            attributes["size_mb"] = str(vdisk_data["size"])
        if vdisk_data.get("layout"):
            # Map RAID layout types based on Dell documentation
            layout_map = {
                1: "Unknown",
                2: "RAID-0", 
                3: "RAID-1",
                4: "RAID-5",
                5: "RAID-6",
                6: "RAID-10",
                7: "RAID-50",
                8: "RAID-60",
                9: "Concatenated RAID-1",
                10: "Concatenated RAID-5"
            }
            try:
                layout_int = int(vdisk_data["layout"])
                attributes["raid_level"] = layout_map.get(layout_int, f"Unknown_{layout_int}")
            except (ValueError, TypeError):
                attributes["raid_level"] = str(vdisk_data["layout"])
        
        return attributes if attributes else None


class IdracPhysicalDiskSensor(IdracSensor):
    """Dell iDRAC physical disk sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pdisk_index: int,
    ) -> None:
        """Initialize the physical disk sensor."""
        sensor_key = f"pdisk_{pdisk_index}"
        sensor_name = f"Physical Disk {pdisk_index}"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            None,
            SensorDeviceClass.ENUM,
        )
        self._pdisk_index = pdisk_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the physical disk."""
        if self.coordinator.data is None or "physical_disks" not in self.coordinator.data:
            return None
        
        pdisk_data = self.coordinator.data["physical_disks"].get(self._sensor_key)
        if pdisk_data is None:
            return None
        
        state_value = pdisk_data.get("state")
        if state_value is not None:
            # Map Dell physical disk states
            state_map = {
                1: "unknown",
                2: "ready",
                3: "online",
                4: "foreign",
                5: "offline",
                6: "blocked",
                7: "failed",
                8: "non_raid",
                9: "removed"
            }
            try:
                state_int = int(state_value)
                return state_map.get(state_int, f"unknown_{state_int}")
            except (ValueError, TypeError):
                return str(state_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "physical_disks" not in self.coordinator.data:
            return None
        
        pdisk_data = self.coordinator.data["physical_disks"].get(self._sensor_key)
        if pdisk_data is None:
            return None
        
        attributes = {}
        if pdisk_data.get("capacity"):
            attributes["capacity_mb"] = str(pdisk_data["capacity"])
        if pdisk_data.get("used_space"):
            attributes["used_space_mb"] = str(pdisk_data["used_space"])
        if pdisk_data.get("serial"):
            attributes["serial_number"] = str(pdisk_data["serial"])
        
        return attributes if attributes else None


class IdracStorageControllerSensor(IdracSensor):
    """Dell iDRAC storage controller sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the storage controller sensor."""
        sensor_key = f"controller_{controller_index}"
        sensor_name = f"Storage Controller {controller_index}"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            None,
            SensorDeviceClass.ENUM,
        )
        self._controller_index = controller_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the storage controller."""
        if self.coordinator.data is None or "storage_controllers" not in self.coordinator.data:
            return None
        
        controller_data = self.coordinator.data["storage_controllers"].get(self._sensor_key)
        if controller_data is None:
            return None
        
        state_value = controller_data.get("state")
        if state_value is not None:
            # Map Dell controller states
            state_map = {
                1: "unknown",
                2: "ready",
                3: "failed",
                4: "online",
                5: "offline",
                6: "degraded"
            }
            try:
                state_int = int(state_value)
                mapped_state = state_map.get(state_int, f"unknown_{state_int}")
                
                # Debug logging to show state mapping and diagnostic info
                controller_data = self.coordinator.data["storage_controllers"].get(self._sensor_key)
                rollup_status = controller_data.get("rollup_status") if controller_data else None
                controller_name = controller_data.get("name") if controller_data else None
                
                _LOGGER.debug(
                    f"Storage Controller {self._controller_index} - State mapping: "
                    f"raw value {state_value} -> integer {state_int} -> '{mapped_state}', "
                    f"Rollup status: {rollup_status}, Name: {controller_name}"
                )
                
                return mapped_state
            except (ValueError, TypeError):
                _LOGGER.debug(
                    f"Storage Controller {self._controller_index} - Failed to convert state value "
                    f"'{state_value}' (type: {type(state_value)}) to integer, returning as string"
                )
                return str(state_value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "storage_controllers" not in self.coordinator.data:
            return None
        
        controller_data = self.coordinator.data["storage_controllers"].get(self._sensor_key)
        if controller_data is None:
            return None
        
        attributes = {}
        
        # Battery status
        battery_state = controller_data.get("battery_state")
        if battery_state is not None:
            # Map battery states
            battery_map = {
                1: "unknown",
                2: "ready",
                3: "failed",
                4: "degraded",
                5: "missing",
                6: "charging",
                7: "below_threshold"
            }
            try:
                battery_int = int(battery_state)
                attributes["battery_status"] = battery_map.get(battery_int, f"unknown_{battery_int}")
            except (ValueError, TypeError):
                attributes["battery_status"] = str(battery_state)
        
        # Rollup status (overall health)
        rollup_status = controller_data.get("rollup_status")
        if rollup_status is not None:
            rollup_map = {
                1: "other",
                2: "unknown",
                3: "ok",
                4: "non_critical",
                5: "critical",
                6: "non_recoverable"
            }
            try:
                rollup_int = int(rollup_status)
                attributes["overall_health"] = rollup_map.get(rollup_int, f"unknown_{rollup_int}")
            except (ValueError, TypeError):
                attributes["overall_health"] = str(rollup_status)
        
        # Controller information
        if controller_data.get("name"):
            attributes["controller_name"] = str(controller_data["name"])
        if controller_data.get("firmware_version"):
            attributes["firmware_version"] = str(controller_data["firmware_version"])
        if controller_data.get("cache_size"):
            attributes["cache_size_mb"] = str(controller_data["cache_size"])
        if controller_data.get("rebuild_rate"):
            attributes["rebuild_rate_percent"] = str(controller_data["rebuild_rate"])
        
        return attributes if attributes else None


class IdracMemoryHealthSensor(IdracSensor):
    """Dell iDRAC memory health sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        memory_index: int,
    ) -> None:
        """Initialize the memory health sensor."""
        sensor_key = f"memory_{memory_index}"
        sensor_name = f"Memory Module {memory_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            None,
            SensorDeviceClass.ENUM,
        )
        self._memory_index = memory_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the memory module."""
        if self.coordinator.data is None or "memory_health" not in self.coordinator.data:
            return None
        
        health_value = self.coordinator.data["memory_health"].get(self._sensor_key)
        if health_value is not None:
            # Map Dell memory health states
            state_map = {
                1: "other",
                2: "unknown", 
                3: "ok",
                4: "non_critical",
                5: "critical",
                6: "non_recoverable"
            }
            try:
                health_int = int(health_value)
                return state_map.get(health_int, f"unknown_{health_int}")
            except (ValueError, TypeError):
                return str(health_value)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "memory_health" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["memory_health"]
            and self.coordinator.data["memory_health"][self._sensor_key] is not None
        )