"""Binary sensor platform for Dell iDRAC integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    DOMAIN,
)
from .coordinator_snmp import SNMPDataUpdateCoordinator
from .coordinator_redfish import RedfishDataUpdateCoordinator


def _get_device_name_prefix(coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator) -> str:
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
    """Set up the Dell iDRAC binary sensors."""
    coordinators = hass.data[DOMAIN][config_entry.entry_id]
    snmp_coordinator = coordinators["snmp"]
    redfish_coordinator = coordinators["redfish"]
    
    def get_coordinator_for_category(category: str):
        """Determine which coordinator to use for a given data category."""
        # SNMP categories
        snmp_categories_list = [
            "temperatures", "fans", "power_supplies", "voltages", "memory",
            "virtual_disks", "physical_disks", "storage_controllers", 
            "system_voltages", "power_consumption", "intrusion_detection",
            "battery", "processors"
        ]
        
        # Redfish categories
        redfish_categories_list = [
            "system_info", "manager_info", "chassis_info", "power_redundancy",
            "system_health", "indicator_led_state", "chassis_intrusion"
        ]
        
        # Check which coordinator actually has data for this category
        if category in snmp_categories_list:
            if snmp_coordinator.data and category in snmp_coordinator.data and snmp_coordinator.data[category]:
                return snmp_coordinator
        
        if category in redfish_categories_list:
            if redfish_coordinator.data and category in redfish_coordinator.data and redfish_coordinator.data[category]:
                return redfish_coordinator
                
        # Fallback: use whichever coordinator has the data
        if snmp_coordinator.data and category in snmp_coordinator.data and snmp_coordinator.data[category]:
            return snmp_coordinator
        elif redfish_coordinator.data and category in redfish_coordinator.data and redfish_coordinator.data[category]:
            return redfish_coordinator
            
        return None
    
    entities: list[IdracBinarySensor] = []
    
    # System health sensors (typically from Redfish)
    system_coordinator = get_coordinator_for_category("system_health") or redfish_coordinator
    entities.extend([
        IdracSystemHealthBinarySensor(system_coordinator, config_entry),
        IdracPowerStateBinarySensor(system_coordinator, config_entry),
    ])
    
    # Intrusion sensors 
    intrusion_coordinator = get_coordinator_for_category("chassis_intrusion") or redfish_coordinator
    entities.append(IdracSystemIntrusionBinarySensor(intrusion_coordinator, config_entry))
    
    # PSU redundancy (typically from Redfish)
    redundancy_coordinator = get_coordinator_for_category("power_redundancy") or redfish_coordinator
    entities.append(IdracPsuRedundancyBinarySensor(redundancy_coordinator, config_entry))

    # Add PSU status binary sensors
    psu_coordinator = get_coordinator_for_category("power_supplies") or snmp_coordinator
    for psu_index in config_entry.data.get(CONF_DISCOVERED_PSUS, []):
        entities.append(
            IdracPsuStatusBinarySensor(psu_coordinator, config_entry, psu_index)
        )

    # Add memory health binary sensors
    memory_coordinator = get_coordinator_for_category("memory") or snmp_coordinator
    for memory_index in config_entry.data.get(CONF_DISCOVERED_MEMORY, []):
        entities.append(
            IdracMemoryHealthBinarySensor(memory_coordinator, config_entry, memory_index)
        )

    # Add virtual disk binary sensors
    vdisk_coordinator = get_coordinator_for_category("virtual_disks") or snmp_coordinator
    for vdisk_index in config_entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, []):
        entities.append(
            IdracVirtualDiskBinarySensor(vdisk_coordinator, config_entry, vdisk_index)
        )

    # Add physical disk binary sensors
    pdisk_coordinator = get_coordinator_for_category("physical_disks") or snmp_coordinator
    for pdisk_index in config_entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, []):
        entities.append(
            IdracPhysicalDiskBinarySensor(pdisk_coordinator, config_entry, pdisk_index)
        )

    # Add storage controller binary sensors
    controller_coordinator = get_coordinator_for_category("storage_controllers") or snmp_coordinator
    for controller_index in config_entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, []):
        entities.extend([
            IdracStorageControllerBinarySensor(controller_coordinator, config_entry, controller_index),
            IdracControllerBatteryBinarySensor(controller_coordinator, config_entry, controller_index),
        ])
    
    # Note: Voltage status binary sensors removed - voltage status is covered by regular voltage sensors

    async_add_entities(entities)


class IdracBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Dell iDRAC binary sensors."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
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
        device_prefix = _get_device_name_prefix(coordinator)
        self._attr_name = f"{device_prefix} {sensor_name}"
        # Use stable unique_id based on device_id and sensor key
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        self._attr_device_class = device_class

        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.is_on is not None


class IdracPsuStatusBinarySensor(IdracBinarySensor):
    """Dell iDRAC PSU status binary sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        psu_index: int,
    ) -> None:
        """Initialize the PSU status binary sensor."""
        sensor_key = f"psu_{psu_index}"
        # Extract numeric index for consistent naming
        psu_index = psu_index.replace('psu_', '') if str(psu_index).startswith('psu_') else psu_index
        sensor_name = f"Power Supply {psu_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:power-plug"

    @property
    def is_on(self) -> bool | None:
        """Return True if PSU has a problem."""
        if self.coordinator.data is None or "power_supplies" not in self.coordinator.data:
            return None
        
        psu_data = self.coordinator.data["power_supplies"].get(self._sensor_key)
        if psu_data is None:
            return None
        
        # Handle both SNMP nested format and direct status format
        if isinstance(psu_data, dict):
            status_value = psu_data.get("status")
        else:
            status_value = psu_data
            
        if status_value is None:
            return None
            
        # Handle both string and numeric status values
        if isinstance(status_value, str):
            # String status: "ok", "critical", "warning", etc.
            return status_value.lower() not in ["ok", "normal", "good"]
        else:
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
        if self.coordinator.data is None or "power_supplies" not in self.coordinator.data:
            return None
        
        psu_data = self.coordinator.data["power_supplies"].get(self._sensor_key)
        if psu_data is None:
            return None
        
        attributes = {}
        
        # Handle nested PSU data structure
        if isinstance(psu_data, dict):
            status_value = psu_data.get("status")
            # Add additional PSU information if available
            if "name" in psu_data:
                attributes["psu_name"] = psu_data["name"]
            if "power_capacity_watts" in psu_data:
                attributes["power_capacity_watts"] = psu_data["power_capacity_watts"]
            if "power_output_watts" in psu_data:
                attributes["power_output_watts"] = psu_data["power_output_watts"]
        else:
            status_value = psu_data
            
        if status_value is not None:
            if isinstance(status_value, str):
                attributes["status_text"] = status_value
            else:
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
                    
                    attributes.update({
                        "status_code": status_int,
                        "status_text": status_text,
                    })
                except (ValueError, TypeError):
                    attributes["raw_value"] = str(status_value)
        
        return attributes if attributes else None


class IdracSystemHealthBinarySensor(IdracBinarySensor):
    """Dell iDRAC system health binary sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the system health binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "system_health",
            "Overall System Health",
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:server"

    @property
    def is_on(self) -> bool | None:
        """Return True if system has a health problem."""
        if self.coordinator.data is None:
            return None
        
        health_data = self.coordinator.data.get("system_health")
        if health_data is not None:
            # Handle Redfish data format (dictionary with overall_status)
            if isinstance(health_data, dict):
                overall_status = health_data.get("overall_status")
                if overall_status:
                    # "Critical" or "Warning" means problem, "OK" means no problem
                    return overall_status in ["Critical", "Warning"]
            # Handle SNMP data format (integer)
            else:
                try:
                    health_int = int(health_data)
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        vdisk_index: int,
    ) -> None:
        """Initialize the virtual disk binary sensor."""
        sensor_key = f"vdisk_{vdisk_index}"
        sensor_name = f"Virtual Disk {vdisk_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:harddisk"
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        pdisk_index: int,
    ) -> None:
        """Initialize the physical disk binary sensor."""
        sensor_key = f"pdisk_{pdisk_index}"
        sensor_name = f"Physical Disk {pdisk_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:harddisk"
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the storage controller binary sensor."""
        sensor_key = f"controller_{controller_index}"
        sensor_name = f"Storage Controller {controller_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:expansion-card"
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        controller_index: int,
    ) -> None:
        """Initialize the controller battery binary sensor."""
        sensor_key = f"controller_{controller_index}_battery"
        sensor_name = f"Storage Controller {controller_index} Battery Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.BATTERY,
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:battery"
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the system intrusion binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "system_intrusion",
            "Chassis Intrusion Detection",
            BinarySensorDeviceClass.SAFETY,  # "On" means intrusion detected
        )
        self._attr_icon = "mdi:shield-alert"

    @property
    def is_on(self) -> bool | None:
        """Return True if chassis intrusion is detected, None if sensor status unknown."""
        if self.coordinator.data is None:
            return None
        
        # Try Redfish data format first
        intrusion_data = self.coordinator.data.get("chassis_intrusion")
        if intrusion_data is not None:
            if isinstance(intrusion_data, dict):
                status = intrusion_data.get("status")
                if status:
                    # According to Redfish spec, valid IntrusionSensor values are:
                    # "Normal", "HardwareIntrusion", "TamperingDetected"
                    if status in ["HardwareIntrusion", "TamperingDetected"]:
                        return True  # Intrusion detected
                    elif status == "Normal":
                        return False  # No intrusion
                    else:
                        # "Unknown" status likely means:
                        # 1. Physical intrusion sensor not present on this chassis
                        # 2. Sensor is not supported/enabled  
                        # 3. Sensor malfunction
                        # For security monitoring: return None (unavailable) is more accurate
                        # than assuming False (no intrusion) when sensor status is unknown
                        return None
        
        # Try alternative chassis info location
        chassis_info = self.coordinator.data.get("chassis_info", {})
        intrusion_sensor = chassis_info.get("intrusion_sensor")
        if intrusion_sensor is not None:
            if intrusion_sensor in ["HardwareIntrusion", "TamperingDetected"]:
                return True
            elif intrusion_sensor == "Normal":
                return False
            else:
                # "Unknown" - sensor status cannot be determined
                return None
        
        # Fallback to SNMP data format
        intrusion_value = self.coordinator.data.get("system_intrusion")
        if intrusion_value is not None:
            try:
                intrusion_int = int(intrusion_value)
                # Dell iDRAC intrusion values: 1=secure, 2=off (disabled), 3=breach_detected
                if intrusion_int == 1:
                    return False  # Secure
                elif intrusion_int == 3:
                    return True   # Breach detected
                else:
                    return None   # Unknown/disabled
            except (ValueError, TypeError):
                return None
        
        # If no intrusion data found, sensor is not available
        return None


class IdracPsuRedundancyBinarySensor(IdracBinarySensor):
    """Dell iDRAC PSU redundancy binary sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the PSU redundancy binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "psu_redundancy",
            "PSU Redundancy",
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:power-plug-battery"

    @property
    def is_on(self) -> bool | None:
        """Return True if PSU has a problem."""
        if self.coordinator.data is None:
            return None
        
        # Try Redfish data format first
        redundancy_data = self.coordinator.data.get("power_redundancy")
        if redundancy_data is not None:
            if isinstance(redundancy_data, dict):
                status = redundancy_data.get("status")
                if status:
                    # "Critical" or "Warning" means problem, "OK" means no problem
                    return status in ["Critical", "Warning"]
        
        # Fallback to SNMP data format
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
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power state binary sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "power_state",
            "Server Power State",
            BinarySensorDeviceClass.POWER,  # "On" means powered on, "Off" means powered off
        )
        self._attr_icon = "mdi:power"

    @property
    def is_on(self) -> bool | None:
        """Return True if server is powered on."""
        if self.coordinator.data is None:
            return None
        
        power_state = self.coordinator.data.get("system_info", {}).get("power_state")
        if power_state is not None:
            # Handle Redfish string format
            if isinstance(power_state, str):
                return power_state.lower() == "on"
            # Handle SNMP integer format
            else:
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
        
        power_state = self.coordinator.data.get("system_info", {}).get("power_state")
        if power_state is not None:
            # Handle Redfish string format
            if isinstance(power_state, str):
                return {
                    "power_state": power_state,
                    "format": "redfish"
                }
            # Handle SNMP integer format
            else:
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
                        "format": "snmp"
                    }
                except (ValueError, TypeError):
                    return {"raw_value": str(power_state)}
        return None


class IdracMemoryHealthBinarySensor(IdracBinarySensor):
    """Dell iDRAC memory health binary sensor."""

    def __init__(
        self,
        coordinator: SNMPDataUpdateCoordinator | RedfishDataUpdateCoordinator,
        config_entry: ConfigEntry,
        memory_index: int,
    ) -> None:
        """Initialize the memory health binary sensor."""
        sensor_key = f"memory_{memory_index}"
        sensor_name = f"Memory Module {memory_index} Health"
        super().__init__(
            coordinator,
            config_entry,
            sensor_key,
            sensor_name,
            BinarySensorDeviceClass.PROBLEM,  # "On" means problem detected, "Off" means OK
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:memory"

    @property
    def is_on(self) -> bool | None:
        """Return True if memory module has a problem."""
        if self.coordinator.data is None or "memory_health" not in self.coordinator.data:
            return None
        
        memory_data = self.coordinator.data["memory_health"].get(self._sensor_key)
        if memory_data is None:
            return None
        
        # Handle both SNMP nested format and direct status format
        if isinstance(memory_data, dict):
            health_value = memory_data.get("status")
        else:
            health_value = memory_data
            
        if health_value is None:
            return None
            
        # Handle both string and numeric health values
        if isinstance(health_value, str):
            # String health: "ok", "critical", "warning", etc.
            return health_value.lower() not in ["ok", "normal", "good", "ready"]
        else:
            try:
                health_int = int(health_value)
                # Dell iDRAC memory health values: 2=ready/normal, 3=ok are both healthy
                # Only 1=other, 4=non_critical, 5=critical, 6=non_recoverable are problems
                return health_int not in [2, 3]
            except (ValueError, TypeError):
                return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional state attributes."""
        if self.coordinator.data is None or "memory_health" not in self.coordinator.data:
            return None
        
        memory_data = self.coordinator.data["memory_health"].get(self._sensor_key)
        if memory_data is None:
            return None
        
        attributes = {}
        
        # Handle nested memory data structure
        if isinstance(memory_data, dict):
            health_value = memory_data.get("status")
            # Add additional memory information if available
            if "name" in memory_data:
                attributes["memory_name"] = memory_data["name"]
            if "size_kb" in memory_data:
                attributes["size_kb"] = memory_data["size_kb"]
        else:
            health_value = memory_data
            
        if health_value is not None:
            if isinstance(health_value, str):
                attributes["health_text"] = health_value
            else:
                try:
                    health_int = int(health_value)
                    # Map Dell iDRAC memory health values to readable strings
                    health_map = {
                        1: "other",
                        2: "ready", 
                        3: "ok",
                        4: "non_critical",
                        5: "critical",
                        6: "non_recoverable"
                    }
                    health_text = health_map.get(health_int, "unknown")
                    
                    attributes.update({
                        "health_code": health_int,
                        "health_text": health_text,
                    })
                except (ValueError, TypeError):
                    attributes["raw_value"] = str(health_value)
        
        return attributes if attributes else None

