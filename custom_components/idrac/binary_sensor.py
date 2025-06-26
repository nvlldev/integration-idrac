"""Binary sensor platform for Dell iDRAC integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    DOMAIN,
)
from .coordinator import IdracDataUpdateCoordinator


def _get_device_name_prefix(host: str) -> str:
    """Get device name prefix for entity naming."""
    return f"Dell iDRAC ({host})"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Dell iDRAC binary sensors."""
    coordinator: IdracDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: list[IdracBinarySensor] = [
        # System health sensors
        IdracSystemHealthBinarySensor(coordinator, config_entry),
        IdracSystemIntrusionBinarySensor(coordinator, config_entry),
        IdracPsuRedundancyBinarySensor(coordinator, config_entry),
        IdracPowerStateBinarySensor(coordinator, config_entry),
    ]

    # Add PSU status binary sensors
    for psu_index in config_entry.data.get(CONF_DISCOVERED_PSUS, []):
        entities.append(
            IdracPsuStatusBinarySensor(coordinator, config_entry, psu_index)
        )

    # Add memory health binary sensors
    for memory_index in config_entry.data.get(CONF_DISCOVERED_MEMORY, []):
        entities.append(
            IdracMemoryHealthBinarySensor(coordinator, config_entry, memory_index)
        )

    # Add virtual disk binary sensors
    for vdisk_index in config_entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, []):
        entities.append(
            IdracVirtualDiskBinarySensor(coordinator, config_entry, vdisk_index)
        )

    # Add physical disk binary sensors
    for pdisk_index in config_entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, []):
        entities.append(
            IdracPhysicalDiskBinarySensor(coordinator, config_entry, pdisk_index)
        )

    # Add storage controller binary sensors
    for controller_index in config_entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, []):
        entities.extend([
            IdracStorageControllerBinarySensor(coordinator, config_entry, controller_index),
            IdracControllerBatteryBinarySensor(coordinator, config_entry, controller_index),
        ])

    async_add_entities(entities)


class IdracBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Dell iDRAC binary sensors."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
        sensor_name: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        host = config_entry.data[CONF_HOST]
        port = config_entry.data[CONF_PORT]
        device_id = f"{host}:{port}"
        
        # Include device prefix in name for proper entity_id generation
        device_prefix = _get_device_name_prefix(host)
        self._attr_name = f"{device_prefix} {sensor_name}"
        # Use stable unique_id based on device_id and sensor key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_device_class = device_class

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Dell iDRAC ({host}:{port})" if port != 161 else f"Dell iDRAC ({host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{host}",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.is_on is not None


class IdracPsuStatusBinarySensor(IdracBinarySensor):
    """Dell iDRAC PSU status binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        psu_index: int,
    ) -> None:
        """Initialize the PSU status binary sensor."""
        sensor_key = f"psu_status_{psu_index}"
        sensor_name = f"PSU {psu_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if PSU has a problem."""
        if self.coordinator.data is None or "psu_statuses" not in self.coordinator.data:
            return None
        
        status_value = self.coordinator.data["psu_statuses"].get(self._sensor_key)
        if status_value is None:
            return None
            
        try:
            status_int = int(status_value)
            # Dell iDRAC status values: 1=other, 2=unknown, 3=ok, 4=non_critical, 5=critical, 6=non_recoverable
            # Return True (problem) for anything other than "ok" (3)
            return status_int != 3
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "psu_statuses" not in self.coordinator.data:
            return None
        
        status_value = self.coordinator.data["psu_statuses"].get(self._sensor_key)
        if status_value is None:
            return None
            
        try:
            status_int = int(status_value)
            # Map Dell iDRAC status values to readable strings
            status_map = {
                1: "other",
                2: "unknown", 
                3: "ok",
                4: "non_critical",
                5: "critical",
                6: "non_recoverable"
            }
            status_text = status_map.get(status_int, "unknown")
            
            return {
                "status_code": status_int,
                "status_text": status_text,
            }
        except (ValueError, TypeError):
            return {"raw_value": str(status_value)}


class IdracSystemHealthBinarySensor(IdracBinarySensor):
    """Dell iDRAC system health binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the system health binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "system_health",
            "System Health",
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if system has a health problem."""
        if self.coordinator.data is None:
            return None
        
        health_value = self.coordinator.data.get("system_health")
        if health_value is not None:
            try:
                health_int = int(health_value)
                # Dell iDRAC health values: 3=ok, others indicate problems
                return health_int != 3
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return None
        
        health_value = self.coordinator.data.get("system_health")
        if health_value is not None:
            try:
                health_int = int(health_value)
                # Map Dell iDRAC health values to readable strings
                health_map = {
                    1: "other",
                    2: "unknown", 
                    3: "ok",
                    4: "non_critical",
                    5: "critical",
                    6: "non_recoverable"
                }
                health_text = health_map.get(health_int, "unknown")
                
                return {
                    "health_code": health_int,
                    "health_text": health_text,
                }
            except (ValueError, TypeError):
                return {"raw_value": str(health_value)}
        return None


class IdracVirtualDiskBinarySensor(IdracBinarySensor):
    """Dell iDRAC virtual disk binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        vdisk_index: int,
    ) -> None:
        """Initialize the virtual disk binary sensor."""
        sensor_key = f"vdisk_{vdisk_index}"
        sensor_name = f"Virtual Disk {vdisk_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._vdisk_index = vdisk_index

    @property
    def is_on(self) -> bool | None:
        """Return true if the virtual disk has a problem."""
        if self.coordinator.data is None or "virtual_disks" not in self.coordinator.data:
            return None
        
        vdisk_data = self.coordinator.data["virtual_disks"].get(self._sensor_key)
        if vdisk_data is None:
            return None
        
        state_value = vdisk_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                # True (problem) for: 1, 3, 4, 6 (unknown, degraded, failed, offline)
                # False (OK) for: 2 (online)
                return state_int != 2
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "virtual_disks" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["virtual_disks"]
        )


class IdracPhysicalDiskBinarySensor(IdracBinarySensor):
    """Dell iDRAC physical disk binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pdisk_index: int,
    ) -> None:
        """Initialize the physical disk binary sensor."""
        sensor_key = f"pdisk_{pdisk_index}"
        sensor_name = f"Physical Disk {pdisk_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._pdisk_index = pdisk_index

    @property
    def is_on(self) -> bool | None:
        """Return true if the physical disk has a problem."""
        if self.coordinator.data is None or "physical_disks" not in self.coordinator.data:
            return None
        
        pdisk_data = self.coordinator.data["physical_disks"].get(self._sensor_key)
        if pdisk_data is None:
            return None
        
        state_value = pdisk_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                # True (problem) for: 1, 4, 5, 6, 7, 8, 9 (unknown, foreign, offline, blocked, failed, non_raid, removed)
                # False (OK) for: 2, 3 (ready, online)
                return state_int not in [2, 3]
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "physical_disks" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["physical_disks"]
        )


class IdracStorageControllerBinarySensor(IdracBinarySensor):
    """Dell iDRAC storage controller binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the storage controller binary sensor."""
        sensor_key = f"controller_{controller_index}"
        sensor_name = f"Storage Controller {controller_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._controller_index = controller_index

    @property
    def is_on(self) -> bool | None:
        """Return true if the storage controller has a problem."""
        if self.coordinator.data is None or "storage_controllers" not in self.coordinator.data:
            return None
        
        controller_data = self.coordinator.data["storage_controllers"].get(self._sensor_key)
        if controller_data is None:
            return None
        
        state_value = controller_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                # True (problem) for: 1, 2, 4, 5, 6 (other, unknown, non_critical, critical, non_recoverable)
                # False (OK) for: 3 (ok)
                return state_int != 3
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
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
        
        # Add state information
        state_value = controller_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                state_map = {
                    1: "other",
                    2: "unknown",
                    3: "ok",
                    4: "non_critical",
                    5: "critical",
                    6: "non_recoverable"
                }
                attributes["status_text"] = state_map.get(state_int, f"unknown_{state_int}")
                attributes["status_code"] = state_int
            except (ValueError, TypeError):
                attributes["status_text"] = str(state_value)
                attributes["raw_value"] = str(state_value)
        
        return attributes if attributes else None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "storage_controllers" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["storage_controllers"]
        )


class IdracControllerBatteryBinarySensor(IdracBinarySensor):
    """Dell iDRAC storage controller battery binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the controller battery binary sensor."""
        sensor_key = f"controller_{controller_index}_battery"
        sensor_name = f"Storage Controller {controller_index} Battery"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.BATTERY,
        )
        self._controller_index = controller_index
        self._controller_key = f"controller_{controller_index}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the controller battery has a problem."""
        if self.coordinator.data is None or "storage_controllers" not in self.coordinator.data:
            return None
        
        controller_data = self.coordinator.data["storage_controllers"].get(self._controller_key)
        if controller_data is None:
            return None
        
        battery_state = controller_data.get("battery_state")
        if battery_state is not None:
            try:
                battery_int = int(battery_state)
                # True (problem) for: 1, 3, 4, 5, 7 (unknown, failed, degraded, missing, below_threshold)
                # False (OK) for: 2, 6 (ready, charging)
                return battery_int not in [2, 6]
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "storage_controllers" in self.coordinator.data
            and self._controller_key in self.coordinator.data["storage_controllers"]
            and self.coordinator.data["storage_controllers"][self._controller_key].get("battery_state") is not None
        )


class IdracSystemIntrusionBinarySensor(IdracBinarySensor):
    """Dell iDRAC system intrusion binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the system intrusion binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "system_intrusion",
            "Chassis Intrusion",
            BinarySensorDeviceClass.SAFETY,  # "On" means intrusion detected
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if chassis intrusion is detected."""
        if self.coordinator.data is None:
            return None
        
        intrusion_value = self.coordinator.data.get("system_intrusion")
        if intrusion_value is not None:
            try:
                intrusion_int = int(intrusion_value)
                # Dell iDRAC intrusion values: 1=secure, 2=breach_detected
                return intrusion_int == 2
            except (ValueError, TypeError):
                return None
        return None


class IdracPsuRedundancyBinarySensor(IdracBinarySensor):
    """Dell iDRAC PSU redundancy binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the PSU redundancy binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "psu_redundancy",
            "Power Supply Redundancy",
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if PSU has a problem."""
        if self.coordinator.data is None:
            return None
        
        redundancy_value = self.coordinator.data.get("psu_redundancy")
        if redundancy_value is not None:
            try:
                redundancy_int = int(redundancy_value)
                # Dell iDRAC PSU status values: 3=ok, others indicate problems
                return redundancy_int != 3
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return None
        
        redundancy_value = self.coordinator.data.get("psu_redundancy")
        if redundancy_value is not None:
            try:
                redundancy_int = int(redundancy_value)
                # Map Dell iDRAC PSU status values to readable strings
                status_map = {
                    1: "other",
                    2: "unknown", 
                    3: "ok",
                    4: "non_critical",
                    5: "critical",
                    6: "non_recoverable"
                }
                status_text = status_map.get(redundancy_int, "unknown")
                
                return {
                    "status_code": redundancy_int,
                    "status_text": status_text,
                }
            except (ValueError, TypeError):
                return {"raw_value": str(redundancy_value)}
        return None


class IdracPowerStateBinarySensor(IdracBinarySensor):
    """Dell iDRAC power state binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power state binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "power_state",
            "Power State",
            BinarySensorDeviceClass.POWER,  # "On" means powered on, "Off" means powered off
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if server is powered on."""
        if self.coordinator.data is None:
            return None
        
        power_state = self.coordinator.data.get("system_power_state")
        if power_state is not None:
            try:
                power_int = int(power_state)
                # Dell iDRAC power states: 1=on, 2=off
                return power_int == 1
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return None
        
        power_state = self.coordinator.data.get("system_power_state")
        if power_state is not None:
            try:
                power_int = int(power_state)
                # Map Dell iDRAC power states to readable strings
                power_map = {
                    1: "on",
                    2: "off",
                    3: "powering_on",
                    4: "powering_off",
                }
                power_text = power_map.get(power_int, "unknown")
                
                return {
                    "power_code": power_int,
                    "power_text": power_text,
                }
            except (ValueError, TypeError):
                return {"raw_value": str(power_state)}
        return None


class IdracMemoryHealthBinarySensor(IdracBinarySensor):
    """Dell iDRAC memory health binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        memory_index: int,
    ) -> None:
        """Initialize the memory health binary sensor."""
        sensor_key = f"memory_health_{memory_index}"
        sensor_name = f"Memory {memory_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if memory module has a problem."""
        if self.coordinator.data is None or "memory_health" not in self.coordinator.data:
            return None
        
        health_value = self.coordinator.data["memory_health"].get(self._sensor_key)
        if health_value is not None:
            try:
                health_int = int(health_value)
                # Dell iDRAC memory health values: 3=ok, others indicate problems
                return health_int != 3
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "memory_health" not in self.coordinator.data:
            return None
        
        health_value = self.coordinator.data["memory_health"].get(self._sensor_key)
        if health_value is not None:
            try:
                health_int = int(health_value)
                # Map Dell iDRAC health values to readable strings
                health_map = {
                    1: "other",
                    2: "unknown", 
                    3: "ok",
                    4: "non_critical",
                    5: "critical",
                    6: "non_recoverable"
                }
                health_text = health_map.get(health_int, "unknown")
                
                return {
                    "health_code": health_int,
                    "health_text": health_text,
                }
            except (ValueError, TypeError):
                return {"raw_value": str(health_value)}
        return None


class IdracVirtualDiskBinarySensor(IdracBinarySensor):
    """Dell iDRAC virtual disk binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        vdisk_index: int,
    ) -> None:
        """Initialize the virtual disk binary sensor."""
        sensor_key = f"vdisk_{vdisk_index}"
        sensor_name = f"Virtual Disk {vdisk_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._vdisk_index = vdisk_index

    @property
    def is_on(self) -> bool | None:
        """Return true if the virtual disk has a problem."""
        if self.coordinator.data is None or "virtual_disks" not in self.coordinator.data:
            return None
        
        vdisk_data = self.coordinator.data["virtual_disks"].get(self._sensor_key)
        if vdisk_data is None:
            return None
        
        state_value = vdisk_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                # True (problem) for: 1, 3, 4, 6 (unknown, degraded, failed, offline)
                # False (OK) for: 2 (online)
                return state_int != 2
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "virtual_disks" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["virtual_disks"]
        )


class IdracPhysicalDiskBinarySensor(IdracBinarySensor):
    """Dell iDRAC physical disk binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pdisk_index: int,
    ) -> None:
        """Initialize the physical disk binary sensor."""
        sensor_key = f"pdisk_{pdisk_index}"
        sensor_name = f"Physical Disk {pdisk_index} Status"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._pdisk_index = pdisk_index

    @property
    def is_on(self) -> bool | None:
        """Return true if the physical disk has a problem."""
        if self.coordinator.data is None or "physical_disks" not in self.coordinator.data:
            return None
        
        pdisk_data = self.coordinator.data["physical_disks"].get(self._sensor_key)
        if pdisk_data is None:
            return None
        
        state_value = pdisk_data.get("state")
        if state_value is not None:
            try:
                state_int = int(state_value)
                # True (problem) for: 1, 4, 5, 6, 7, 8, 9 (unknown, foreign, offline, blocked, failed, non_raid, removed)
                # False (OK) for: 2, 3 (ready, online)
                return state_int not in [2, 3]
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "physical_disks" in self.coordinator.data
            and self._sensor_key in self.coordinator.data["physical_disks"]
        )




class IdracControllerBatteryBinarySensor(IdracBinarySensor):
    """Dell iDRAC storage controller battery binary sensor."""

    def __init__(
        self,
        coordinator: IdracDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the controller battery binary sensor."""
        sensor_key = f"controller_{controller_index}_battery"
        sensor_name = f"Storage Controller {controller_index} Battery"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.BATTERY,
        )
        self._controller_index = controller_index
        self._controller_key = f"controller_{controller_index}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the controller battery has a problem."""
        if self.coordinator.data is None or "storage_controllers" not in self.coordinator.data:
            return None
        
        controller_data = self.coordinator.data["storage_controllers"].get(self._controller_key)
        if controller_data is None:
            return None
        
        battery_state = controller_data.get("battery_state")
        if battery_state is not None:
            try:
                battery_int = int(battery_state)
                # True (problem) for: 1, 3, 4, 5, 7 (unknown, failed, degraded, missing, below_threshold)
                # False (OK) for: 2, 6 (ready, charging)
                return battery_int not in [2, 6]
            except (ValueError, TypeError):
                return True  # Unknown state treated as problem
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "storage_controllers" in self.coordinator.data
            and self._controller_key in self.coordinator.data["storage_controllers"]
            and self.coordinator.data["storage_controllers"][self._controller_key].get("battery_state") is not None
        )