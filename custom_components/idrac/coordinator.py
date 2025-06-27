"""DataUpdateCoordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
)
from pysnmp.proto import rfc1902

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_AUTH_PROTOCOL,
    CONF_AUTH_PASSWORD,
    CONF_PRIV_PROTOCOL,
    CONF_PRIV_PASSWORD,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    CONF_CONNECTION_TYPE,
    CONF_REQUEST_TIMEOUT,
    CONF_SESSION_TIMEOUT,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_DETAILED_MEMORY,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    CONF_DISCOVERED_POWER_CONSUMPTION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    DEFAULT_CONNECTION_TYPE,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SESSION_TIMEOUT,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    DOMAIN,
    IDRAC_OIDS,
    PSU_STATUS,
    FAN_STATUS,
    TEMP_STATUS,
    MEMORY_HEALTH_STATUS,
    STORAGE_HEALTH_STATUS,
)
from .redfish_client import RedfishClient, RedfishError

_LOGGER = logging.getLogger(__name__)


def _create_auth_data(entry: ConfigEntry) -> CommunityData | UsmUserData:
    """Create the appropriate authentication data for SNMP."""
    snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
    
    if snmp_version == "v3":
        username = entry.data.get(CONF_USERNAME, "")
        auth_protocol = entry.data.get(CONF_AUTH_PROTOCOL, "none")
        auth_password = entry.data.get(CONF_AUTH_PASSWORD, "")
        priv_protocol = entry.data.get(CONF_PRIV_PROTOCOL, "none")
        priv_password = entry.data.get(CONF_PRIV_PASSWORD, "")
        
        # Map protocol names to pysnmp protocol objects
        auth_proto = None
        if auth_protocol != "none":
            auth_proto = getattr(rfc1902, SNMP_AUTH_PROTOCOLS[auth_protocol], None)
        
        priv_proto = None
        if priv_protocol != "none":
            priv_proto = getattr(rfc1902, SNMP_PRIV_PROTOCOLS[priv_protocol], None)
        
        return UsmUserData(
            userName=username,
            authKey=auth_password if auth_proto else None,
            privKey=priv_password if priv_proto else None,
            authProtocol=auth_proto,
            privProtocol=priv_proto,
        )
    else:
        # SNMP v2c
        community = entry.data.get(CONF_COMMUNITY, "public")
        return CommunityData(community)


class IdracDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Dell iDRAC via Redfish API or SNMP."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data.get(CONF_PORT)
        self.connection_type = entry.data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
        
        # Initialize connection-specific attributes
        if self.connection_type == "redfish":
            self.username = entry.data[CONF_USERNAME]
            self.password = entry.data[CONF_PASSWORD]
            self.verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
            self.request_timeout = entry.data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
            self.session_timeout = entry.data.get(CONF_SESSION_TIMEOUT, DEFAULT_SESSION_TIMEOUT)
            
            # Create Redfish client
            self.client = RedfishClient(
                hass, self.host, self.username, self.password, self.port, self.verify_ssl, 
                self.request_timeout, self.session_timeout
            )
        else:
            # SNMP configuration
            self.snmp_version = entry.data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
            self.community = entry.data.get(CONF_COMMUNITY, "public")
            
            # Store discovered sensors
            self.discovered_fans = entry.data.get(CONF_DISCOVERED_FANS, [])
            self.discovered_cpus = entry.data.get(CONF_DISCOVERED_CPUS, [])
            self.discovered_psus = entry.data.get(CONF_DISCOVERED_PSUS, [])
            self.discovered_voltage_probes = entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])
            self.discovered_memory = entry.data.get(CONF_DISCOVERED_MEMORY, [])
            self.discovered_virtual_disks = entry.data.get(CONF_DISCOVERED_VIRTUAL_DISKS, [])
            self.discovered_physical_disks = entry.data.get(CONF_DISCOVERED_PHYSICAL_DISKS, [])
            self.discovered_storage_controllers = entry.data.get(CONF_DISCOVERED_STORAGE_CONTROLLERS, [])
            self.discovered_detailed_memory = entry.data.get(CONF_DISCOVERED_DETAILED_MEMORY, [])
            self.discovered_system_voltages = entry.data.get(CONF_DISCOVERED_SYSTEM_VOLTAGES, [])
            self.discovered_power_consumption = entry.data.get(CONF_DISCOVERED_POWER_CONSUMPTION, [])

            # Create isolated SNMP engine for this coordinator instance
            self.engine = SnmpEngine()
            self.auth_data = _create_auth_data(entry)
            self.transport_target = UdpTransportTarget((self.host, self.port), timeout=5, retries=1)
            self.context_data = ContextData()
        
        # Store server identification for logging
        self._server_id = f"{self.host}:{self.port}"
        
        # System identification data for device info
        self._device_info = None

        # Get scan interval from options first, then config data, then default
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_fetch_device_info(self) -> dict[str, Any]:
        """Fetch device information for device registry."""
        if self._device_info is not None:
            return self._device_info
        
        _LOGGER.debug("Fetching device info for %s", self._server_id)
        
        device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "manufacturer": "Dell",
            "configuration_url": f"https://{self.host}" if self.connection_type == "redfish" else None,
        }
        
        if self.connection_type == "redfish":
            # Get system information via Redfish
            system_data = await self.client.get_system_info()
            if system_data:
                model = system_data.get("Model")
                serial = system_data.get("SerialNumber")
                bios_version = system_data.get("BiosVersion")
                
                if model:
                    device_info["model"] = model
                    device_info["name"] = f"Dell {model} ({self.host})"
                else:
                    device_info["model"] = "iDRAC"
                    device_info["name"] = f"Dell iDRAC ({self.host})"
                
                if serial:
                    device_info["serial_number"] = serial
                
                if bios_version:
                    device_info["sw_version"] = f"BIOS {bios_version}"
            
            # Get iDRAC manager information
            manager_data = await self.client.get_manager_info()
            if manager_data:
                firmware_version = manager_data.get("FirmwareVersion")
                if firmware_version:
                    device_info["hw_version"] = f"iDRAC {firmware_version}"
        else:
            # Get system information via SNMP
            try:
                model_oid = IDRAC_OIDS["system_model"]
                service_tag_oid = IDRAC_OIDS["system_service_tag"]
                bios_version_oid = IDRAC_OIDS["system_bios_version"]
                
                model = await self._async_snmp_get_string(model_oid)
                service_tag = await self._async_snmp_get_string(service_tag_oid)
                bios_version = await self._async_snmp_get_string(bios_version_oid)
                
                if model:
                    device_info["model"] = model
                    device_info["name"] = f"Dell {model} ({self.host})"
                else:
                    device_info["model"] = "iDRAC"
                    device_info["name"] = f"Dell iDRAC ({self.host})"
                
                if service_tag:
                    device_info["serial_number"] = service_tag
                
                if bios_version:
                    device_info["sw_version"] = f"BIOS {bios_version}"
                    
            except Exception as exc:
                _LOGGER.debug("Could not fetch SNMP device info: %s", exc)
                device_info["model"] = "iDRAC"
                device_info["name"] = f"Dell iDRAC ({self.host})"
        
        self._device_info = device_info
        _LOGGER.debug("Device info: %s", device_info)
        return device_info

    @property 
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info or {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Dell iDRAC ({self.host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{self.host}" if self.connection_type == "redfish" else None,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Redfish API or SNMP."""
        try:
            # Fetch device info on first run
            if self._device_info is None:
                await self._async_fetch_device_info()
            
            if self.connection_type == "redfish":
                return await self._async_update_redfish_data()
            else:
                return await self._async_update_snmp_data()

        except Exception as exc:
            if self.connection_type == "redfish":
                if isinstance(exc, RedfishError):
                    raise UpdateFailed(f"Authentication failed for iDRAC {self._server_id}: {exc}") from exc
                raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc
            else:
                raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc

    async def _async_update_redfish_data(self) -> dict[str, Any]:
        """Update data via Redfish API with concurrent requests for better performance."""
        import asyncio
        
        data = {
            "temperatures": {},
            "fans": {},
            "power_supplies": {},
            "voltages": {},
            "system_info": {},
            "manager_info": {},
            "chassis_info": {},
            "power_redundancy": {},
            "system_health": {},
        }

        # Fetch all data concurrently to improve performance
        try:
            system_task = self.client.get_system_info()
            thermal_task = self.client.get_thermal_info()
            power_task = self.client.get_power_info()
            manager_task = self.client.get_manager_info()
            chassis_task = self.client.get_chassis_info()
            
            # Wait for all main API calls to complete concurrently
            system_data, thermal_data, power_data, manager_data, chassis_data = await asyncio.gather(
                system_task, thermal_task, power_task, manager_task, chassis_task,
                return_exceptions=True
            )
            
            # Handle any exceptions from the concurrent calls
            if isinstance(system_data, Exception):
                _LOGGER.warning("Failed to get system info: %s", system_data)
                system_data = None
            if isinstance(thermal_data, Exception):
                _LOGGER.warning("Failed to get thermal info: %s", thermal_data)
                thermal_data = None
            if isinstance(power_data, Exception):
                _LOGGER.warning("Failed to get power info: %s", power_data)
                power_data = None
            if isinstance(manager_data, Exception):
                _LOGGER.warning("Failed to get manager info: %s", manager_data)
                manager_data = None
            if isinstance(chassis_data, Exception):
                _LOGGER.warning("Failed to get chassis info: %s", chassis_data)
                chassis_data = None
                
        except Exception as exc:
            _LOGGER.error("Error during concurrent Redfish API calls: %s", exc)
            # Fallback to sequential calls if concurrent fails
            system_data = await self.client.get_system_info()
            thermal_data = await self.client.get_thermal_info()
            power_data = await self.client.get_power_info()
            manager_data = await self.client.get_manager_info()
            chassis_data = await self.client.get_chassis_info()

        # Process system information
        if system_data:
            data["system_info"] = {
                "power_state": system_data.get("PowerState"),
                "health": system_data.get("Status", {}).get("Health"),
                "state": system_data.get("Status", {}).get("State"),
                "indicator_led": system_data.get("IndicatorLED"),
                "model": system_data.get("Model"),
                "serial_number": system_data.get("SerialNumber"),
                "bios_version": system_data.get("BiosVersion"),
                "memory_gb": system_data.get("MemorySummary", {}).get("TotalSystemMemoryGiB"),
                "processor_count": system_data.get("ProcessorSummary", {}).get("Count"),
                "processor_model": system_data.get("ProcessorSummary", {}).get("Model"),
            }
            
            # Store LED state separately for easy access
            data["indicator_led_state"] = system_data.get("IndicatorLED")

        # Process thermal information (already fetched concurrently)
        if thermal_data:
            # Process temperatures
            temperatures = thermal_data.get("Temperatures", [])
            for i, temp in enumerate(temperatures):
                if temp.get("ReadingCelsius") is not None:
                    sensor_name = temp.get("Name", f"Temperature {i+1}")
                    data["temperatures"][f"temp_{i+1}"] = {
                        "name": sensor_name,
                        "temperature": temp.get("ReadingCelsius"),
                        "status": temp.get("Status", {}).get("Health"),
                        "upper_threshold_critical": temp.get("UpperThresholdCritical"),
                        "upper_threshold_non_critical": temp.get("UpperThresholdNonCritical"),
                    }

            # Process fans
            fans = thermal_data.get("Fans", [])
            for i, fan in enumerate(fans):
                if fan.get("Reading") is not None:
                    fan_name = fan.get("Name", f"Fan {i+1}")
                    data["fans"][f"fan_{i+1}"] = {
                        "name": fan_name,
                        "speed_rpm": fan.get("Reading"),
                        "speed_percent": fan.get("ReadingUnits") == "Percent" and fan.get("Reading"),
                        "status": fan.get("Status", {}).get("Health"),
                    }

        # Process power information (already fetched concurrently)
        if power_data:
            # Process power consumption
            power_control = power_data.get("PowerControl", [])
            if power_control:
                pc = power_control[0]
                data["power_consumption"] = {
                    "consumed_watts": pc.get("PowerConsumedWatts"),
                    "capacity_watts": pc.get("PowerCapacityWatts"),
                    "average_consumed_watts": pc.get("PowerMetrics", {}).get("AverageConsumedWatts"),
                    "max_consumed_watts": pc.get("PowerMetrics", {}).get("MaxConsumedWatts"),
                    "min_consumed_watts": pc.get("PowerMetrics", {}).get("MinConsumedWatts"),
                }

            # Process power supplies
            power_supplies = power_data.get("PowerSupplies", [])
            for i, psu in enumerate(power_supplies):
                psu_name = psu.get("Name", f"PSU {i+1}")
                data["power_supplies"][f"psu_{i+1}"] = {
                    "name": psu_name,
                    "status": psu.get("Status", {}).get("Health"),
                    "state": psu.get("Status", {}).get("State"),
                    "power_capacity_watts": psu.get("PowerCapacityWatts"),
                    "power_input_watts": psu.get("PowerInputWatts"),
                    "power_output_watts": psu.get("PowerOutputWatts"),
                    "line_input_voltage": psu.get("LineInputVoltage"),
                    "model": psu.get("Model"),
                    "manufacturer": psu.get("Manufacturer"),
                    "firmware_version": psu.get("FirmwareVersion"),
                    "serial_number": psu.get("SerialNumber"),
                }

            # Process voltages
            voltages = power_data.get("Voltages", [])
            for i, voltage in enumerate(voltages):
                if voltage.get("ReadingVolts") is not None:
                    voltage_name = voltage.get("Name", f"Voltage {i+1}")
                    data["voltages"][f"voltage_{i+1}"] = {
                        "name": voltage_name,
                        "reading_volts": voltage.get("ReadingVolts"),
                        "status": voltage.get("Status", {}).get("Health"),
                        "upper_threshold_critical": voltage.get("UpperThresholdCritical"),
                        "upper_threshold_non_critical": voltage.get("UpperThresholdNonCritical"),
                        "lower_threshold_critical": voltage.get("LowerThresholdCritical"),
                        "lower_threshold_non_critical": voltage.get("LowerThresholdNonCritical"),
                    }

        # Process manager information (already fetched concurrently)
        if manager_data:
            data["manager_info"] = {
                "name": manager_data.get("Name"),
                "firmware_version": manager_data.get("FirmwareVersion"),
                "model": manager_data.get("Model"),
                "status": manager_data.get("Status", {}).get("Health"),
                "state": manager_data.get("Status", {}).get("State"),
                "datetime": manager_data.get("DateTime"),
            }

        # Process chassis information (already fetched concurrently)
        if chassis_data:
            # Extract intrusion detection status
            physical_security = chassis_data.get("PhysicalSecurity", {})
            data["chassis_info"] = {
                "chassis_type": chassis_data.get("ChassisType"),
                "manufacturer": chassis_data.get("Manufacturer"),
                "model": chassis_data.get("Model"),
                "serial_number": chassis_data.get("SerialNumber"),
                "status": chassis_data.get("Status", {}).get("Health"),
                "state": chassis_data.get("Status", {}).get("State"),
                # Chassis intrusion detection
                "intrusion_sensor": physical_security.get("IntrusionSensor"),
                "intrusion_sensor_number": physical_security.get("IntrusionSensorNumber"),
                "intrusion_sensor_re_arm": physical_security.get("IntrusionSensorReArm"),
            }
            
            # Store chassis intrusion separately for easy access
            data["chassis_intrusion"] = {
                "status": physical_security.get("IntrusionSensor", "Unknown"),
                "sensor_number": physical_security.get("IntrusionSensorNumber"),
                "re_arm": physical_security.get("IntrusionSensorReArm"),
            }

        # Try to get power subsystem for redundancy info (separate async call)
        try:
            power_subsystem_data = await self.client.get_power_subsystem()
            if power_subsystem_data:
                power_supplies_data = power_subsystem_data.get("PowerSupplies", {})
                redundancy_data = power_supplies_data.get("Redundancy", [])
                
                if redundancy_data:
                    redundancy_info = redundancy_data[0] if isinstance(redundancy_data, list) else redundancy_data
                    data["power_redundancy"] = {
                        "mode": redundancy_info.get("Mode"),
                        "status": redundancy_info.get("Status", {}).get("Health"),
                        "state": redundancy_info.get("Status", {}).get("State"),
                        "redundancy_set": redundancy_info.get("RedundancySet", []),
                        "min_num_needed": redundancy_info.get("MinNumNeeded"),
                        "max_num_supported": redundancy_info.get("MaxNumSupported"),
                    }
                else:
                    # Fallback: analyze power supply status for redundancy
                    power_supplies = data.get("power_supplies", {})
                    total_psus = len(power_supplies)
                    healthy_psus = sum(1 for psu in power_supplies.values() 
                                     if psu.get("status") in ["OK", "ok"])
                    
                    if total_psus > 1:
                        if healthy_psus == total_psus:
                            redundancy_status = "OK"
                        elif healthy_psus >= total_psus // 2:
                            redundancy_status = "Warning"
                        else:
                            redundancy_status = "Critical"
                    else:
                        redundancy_status = "Non-Redundant"
                    
                    data["power_redundancy"] = {
                        "mode": "N+1" if total_psus > 1 else "Non-Redundant",
                        "status": redundancy_status,
                        "total_psus": total_psus,
                        "healthy_psus": healthy_psus,
                    }
        except Exception as exc:
            _LOGGER.debug("Could not get power subsystem data: %s", exc)
            # Fallback power redundancy calculation
            power_supplies = data.get("power_supplies", {})
            total_psus = len(power_supplies)
            healthy_psus = sum(1 for psu in power_supplies.values() 
                             if psu.get("status") in ["OK", "ok"])
            
            if total_psus > 1:
                if healthy_psus == total_psus:
                    redundancy_status = "OK"
                elif healthy_psus >= total_psus // 2:
                    redundancy_status = "Warning"
                else:
                    redundancy_status = "Critical"
            else:
                redundancy_status = "Non-Redundant"
            
            data["power_redundancy"] = {
                "mode": "N+1" if total_psus > 1 else "Non-Redundant",
                "status": redundancy_status,
                "total_psus": total_psus,
                "healthy_psus": healthy_psus,
            }

        # Calculate overall system health
        health_components = []
        
        # System health
        if system_data:
            system_health = system_data.get("Status", {}).get("Health")
            if system_health:
                health_components.append(system_health)
        
        # Chassis health
        if chassis_data:
            chassis_health = chassis_data.get("Status", {}).get("Health")
            if chassis_health:
                health_components.append(chassis_health)
        
        # Power supply health
        for psu_data in data.get("power_supplies", {}).values():
            psu_health = psu_data.get("status")
            if psu_health:
                health_components.append(psu_health)
        
        # Fan health
        for fan_data in data.get("fans", {}).values():
            fan_health = fan_data.get("status")
            if fan_health:
                health_components.append(fan_health)
        
        # Temperature sensor health
        for temp_data in data.get("temperatures", {}).values():
            temp_health = temp_data.get("status")
            if temp_health:
                health_components.append(temp_health)
        
        # Calculate overall health
        if health_components:
            # Check for any critical issues
            if any(health in ["Critical", "critical"] for health in health_components):
                overall_health = "Critical"
            elif any(health in ["Warning", "warning", "OK"] for health in health_components):
                overall_health = "Warning"
            else:
                overall_health = "OK"
        else:
            overall_health = "Unknown"
        
        data["system_health"] = {
            "overall_status": overall_health,
            "component_count": len(health_components),
            "components": health_components,
        }

        return data

    async def _async_update_snmp_data(self) -> dict[str, Any]:
        """Update data via SNMP."""
        data = {
            "temperatures": {},
            "fans": {},
            "power_supplies": {},
            "voltages": {},
            "memory": {},
            "virtual_disks": {},
            "physical_disks": {},
            "storage_controllers": {},
            "system_voltages": {},
            "power_consumption": {},
        }

        # Get CPU temperature sensors
        for cpu_id in self.discovered_cpus:
            temp_reading = await self._async_snmp_get_value(IDRAC_OIDS["temp_probe_reading"].format(index=cpu_id))
            temp_status = await self._async_snmp_get_value(IDRAC_OIDS["temp_probe_status"].format(index=cpu_id))
            temp_location = await self._async_snmp_get_string(IDRAC_OIDS["temp_probe_location"].format(index=cpu_id))
            temp_upper_critical = await self._async_snmp_get_value(IDRAC_OIDS["temp_probe_upper_critical"].format(index=cpu_id))
            temp_upper_warning = await self._async_snmp_get_value(IDRAC_OIDS["temp_probe_upper_warning"].format(index=cpu_id))

            if temp_reading is not None:
                # Convert temperature from tenths of degrees to degrees
                temperature_celsius = temp_reading / 10.0 if temp_reading > 100 else temp_reading
                
                data["temperatures"][f"cpu_temp_{cpu_id}"] = {
                    "name": temp_location or f"CPU {cpu_id} Temperature",
                    "temperature": temperature_celsius,
                    "status": TEMP_STATUS.get(temp_status, "unknown"),
                    "upper_threshold_critical": temp_upper_critical / 10.0 if temp_upper_critical and temp_upper_critical > 100 else temp_upper_critical,
                    "upper_threshold_non_critical": temp_upper_warning / 10.0 if temp_upper_warning and temp_upper_warning > 100 else temp_upper_warning,
                }

        # Get fan sensors
        for fan_id in self.discovered_fans:
            fan_reading = await self._async_snmp_get_value(IDRAC_OIDS["cooling_device_reading"].format(index=fan_id))
            fan_status = await self._async_snmp_get_value(IDRAC_OIDS["cooling_device_status"].format(index=fan_id))
            fan_location = await self._async_snmp_get_string(IDRAC_OIDS["cooling_device_location"].format(index=fan_id))

            if fan_reading is not None:
                data["fans"][f"fan_{fan_id}"] = {
                    "name": fan_location or f"Fan {fan_id}",
                    "speed_rpm": fan_reading,
                    "status": FAN_STATUS.get(fan_status, "unknown"),
                }

        # Get PSU sensors
        for psu_id in self.discovered_psus:
            psu_status = await self._async_snmp_get_value(IDRAC_OIDS["psu_status"].format(index=psu_id))
            psu_location = await self._async_snmp_get_string(IDRAC_OIDS["psu_location"].format(index=psu_id))
            psu_max_output = await self._async_snmp_get_value(IDRAC_OIDS["psu_max_output"].format(index=psu_id))
            psu_current_output = await self._async_snmp_get_value(IDRAC_OIDS["psu_current_output"].format(index=psu_id))

            data["power_supplies"][f"psu_{psu_id}"] = {
                "name": psu_location or f"PSU {psu_id}",
                "status": PSU_STATUS.get(psu_status, "unknown"),
                "power_capacity_watts": psu_max_output,
                "power_output_watts": psu_current_output,
            }

        # Get voltage probe sensors
        for voltage_id in self.discovered_voltage_probes:
            voltage_reading = await self._async_snmp_get_value(IDRAC_OIDS["psu_input_voltage"].format(index=voltage_id))
            voltage_location = await self._async_snmp_get_string(IDRAC_OIDS["psu_location"].format(index=voltage_id))

            if voltage_reading is not None:
                # Convert millivolts to volts
                voltage_volts = voltage_reading / 1000.0 if voltage_reading > 1000 else voltage_reading
                
                data["voltages"][f"psu_voltage_{voltage_id}"] = {
                    "name": f"{voltage_location} Voltage" if voltage_location else f"PSU {voltage_id} Voltage",
                    "reading_volts": voltage_volts,
                    "status": "ok",
                }

        # Get memory sensors
        for memory_id in self.discovered_memory:
            memory_status = await self._async_snmp_get_value(IDRAC_OIDS["memory_status"].format(index=memory_id))
            memory_location = await self._async_snmp_get_string(IDRAC_OIDS["memory_location"].format(index=memory_id))
            memory_size = await self._async_snmp_get_value(IDRAC_OIDS["memory_size"].format(index=memory_id))

            data["memory"][f"memory_{memory_id}"] = {
                "name": memory_location or f"Memory {memory_id}",
                "status": MEMORY_HEALTH_STATUS.get(memory_status, "unknown"),
                "size_kb": memory_size,
            }

        # Get power consumption
        if self.discovered_power_consumption:
            power_current = await self._async_snmp_get_value(IDRAC_OIDS["power_consumption_current"])
            power_peak = await self._async_snmp_get_value(IDRAC_OIDS["power_consumption_peak"])

            if power_current is not None:
                data["power_consumption"] = {
                    "consumed_watts": power_current,
                    "max_consumed_watts": power_peak,
                }

        return data

    async def _async_snmp_get_value(self, oid: str) -> int | None:
        """Get an SNMP value and return as integer."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication:
                _LOGGER.debug("SNMP error indication for OID %s: %s", oid, error_indication)
                return None
            elif error_status:
                _LOGGER.debug("SNMP error status for OID %s: %s", oid, error_status.prettyPrint())
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        _LOGGER.debug("Could not convert SNMP value to int for OID %s: %s", oid, val)
                        return None
            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP value for OID %s: %s", oid, exc)
            return None

    async def _async_snmp_get_string(self, oid: str) -> str | None:
        """Get an SNMP value and return as string."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid)),
            )

            if error_indication:
                _LOGGER.debug("SNMP error indication for OID %s: %s", oid, error_indication)
                return None
            elif error_status:
                _LOGGER.debug("SNMP error status for OID %s: %s", oid, error_status.prettyPrint())
                return None

            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    return str(val).strip()
            return None

        except Exception as exc:
            _LOGGER.debug("Exception getting SNMP string for OID %s: %s", oid, exc)
            return None

    async def async_reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset system via Redfish API."""
        if self.connection_type != "redfish":
            _LOGGER.error("System reset only available via Redfish API")
            return False
            
        try:
            result = await self.client.reset_system(reset_type)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to reset system on %s: %s", self._server_id, exc)
            return False

    async def async_set_indicator_led(self, state: str) -> bool:
        """Set indicator LED state via Redfish API."""
        if self.connection_type != "redfish":
            _LOGGER.error("LED control only available via Redfish API")
            return False
            
        try:
            result = await self.client.set_indicator_led(state)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to set LED on %s: %s", self._server_id, exc)
            return False