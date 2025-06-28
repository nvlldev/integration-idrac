"""Redfish protocol coordinator for Dell iDRAC."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .redfish_client import RedfishClient, RedfishError
from ..const import (
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_REQUEST_TIMEOUT,
    CONF_SESSION_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SESSION_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RedfishCoordinator:
    """Redfish protocol coordinator for Dell iDRAC.
    
    This coordinator handles all Redfish API operations for Dell iDRAC devices.
    It manages SSL connections, performs concurrent API calls for efficiency,
    and provides methods for both data collection and system control.
    
    The coordinator supports:
    - Sensor data collection (temperatures, fans, power, voltages)
    - System information retrieval
    - Device control operations (LED, system reset)
    - Efficient concurrent API calls with connection pooling
    
    Attributes:
        hass: Home Assistant instance.
        entry: Configuration entry.
        host: iDRAC host address.
        client: Redfish API client instance.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Redfish coordinator.
        
        Args:
            hass: Home Assistant instance.
            entry: Configuration entry containing Redfish connection details.
        """
        self.hass = hass
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = int(entry.data.get(CONF_PORT, 443))  # Ensure port is an integer
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
        self.request_timeout = int(entry.data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))
        self.session_timeout = int(entry.data.get(CONF_SESSION_TIMEOUT, DEFAULT_SESSION_TIMEOUT))
        
        # Create Redfish client
        self.client = RedfishClient(
            hass, self.host, self.username, self.password, self.port, self.verify_ssl, 
            self.request_timeout, self.session_timeout
        )
        self._ssl_warmed_up = False
        
        # Store server identification for logging
        self._server_id = f"{self.host}:{self.port}"
        
        # System identification data for device info
        self._device_info = None

    async def get_device_info(self) -> dict[str, Any]:
        """Fetch device information via Redfish API for device registry.
        
        Retrieves system and manager information from the iDRAC to populate
        the Home Assistant device registry. Information includes model, serial
        number, BIOS version, and firmware details.
        
        Returns:
            Dictionary containing device information with keys like 'model',
            'serial_number', 'sw_version', 'hw_version', etc.
        """
        if self._device_info is not None:
            return self._device_info
        
        _LOGGER.debug("Fetching device info for %s", self._server_id)
        
        device_info = {
            "identifiers": {(DOMAIN, self._server_id)},
            "manufacturer": "Dell",
            "configuration_url": f"https://{self.host}",
        }
        
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
        
        self._device_info = device_info
        _LOGGER.debug("Device info: %s", device_info)
        return device_info

    async def get_sensor_data(self) -> dict[str, Any]:
        """Collect all sensor data via Redfish API with concurrent requests.
        
        Performs multiple Redfish API calls concurrently to collect comprehensive
        sensor data including temperatures, fans, power supplies, voltages, and
        system health information. Uses connection pooling and SSL warming for
        optimal performance.
        
        The method collects data from these Redfish endpoints:
        - /redfish/v1/Systems/{id} - System information
        - /redfish/v1/Chassis/{id}/Thermal - Temperature and fan data
        - /redfish/v1/Chassis/{id}/Power - Power and voltage data
        - /redfish/v1/Managers/{id} - Manager/firmware information
        - /redfish/v1/Chassis/{id} - Chassis and intrusion data
        - /redfish/v1/Chassis/{id}/PowerSubsystem - Power redundancy data
        
        Returns:
            Dictionary containing organized sensor data with keys:
            - temperatures: Temperature sensor readings
            - fans: Fan speed and status
            - power_supplies: PSU status and metrics
            - voltages: Voltage readings
            - system_info: System state and specifications
            - manager_info: iDRAC firmware and status
            - chassis_info: Chassis intrusion status
            - power_redundancy: Power redundancy information
            - system_health: Overall system health assessment
        """
        # Pre-warm SSL connection on first run to reduce latency
        if not self._ssl_warmed_up:
            try:
                warmup_start = time.time()
                await self.client.warm_up_connection()
                self._ssl_warmed_up = True
                _LOGGER.debug("SSL warm-up completed in %.2f seconds", time.time() - warmup_start)
            except Exception as exc:
                _LOGGER.debug("SSL warm-up failed, continuing: %s", exc)
                # Continue without warm-up, individual requests will establish connections
                pass
        
        start_time = time.time()
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

        # First validate service root to ensure Redfish is available
        try:
            service_root = await self.client.get_service_root()
            if not service_root:
                _LOGGER.error("Redfish service root unavailable on %s", self._server_id)
                return data
        except Exception as exc:
            _LOGGER.error("Failed to connect to Redfish on %s: %s", self._server_id, exc)
            return data

        # Fetch core sensor data concurrently, prioritizing essential endpoints
        try:
            # Primary concurrent batch - essential sensor data
            _LOGGER.debug("Fetching primary sensor data from %s", self._server_id)
            system_task = self.client.get_system_info()
            thermal_task = self.client.get_thermal_info()
            power_task = self.client.get_power_info()
            
            # Wait for primary data to complete concurrently with timeout
            # Based on real iDRAC testing: endpoints take 4-8 seconds each
            primary_timeout = 12.0  # Allow time for concurrent 5-8s responses
            system_data, thermal_data, power_data = await asyncio.wait_for(
                asyncio.gather(system_task, thermal_task, power_task, return_exceptions=True),
                timeout=primary_timeout
            )
            
            # Check for any critical failures in primary data
            primary_failures = 0
            if isinstance(system_data, Exception):
                _LOGGER.warning("System data failed: %s", system_data)
                system_data = None
                primary_failures += 1
            if isinstance(thermal_data, Exception):
                _LOGGER.warning("Thermal data failed: %s", thermal_data)
                thermal_data = None
                primary_failures += 1
            if isinstance(power_data, Exception):
                _LOGGER.warning("Power data failed: %s", power_data)
                power_data = None
                primary_failures += 1
            
            # Only proceed with secondary data if primary was successful enough
            secondary_start = time.time()
            primary_time = secondary_start - start_time
            
            if primary_failures <= 1 and primary_time < 10.0:
                # Secondary batch - nice-to-have data
                _LOGGER.debug("Fetching secondary data from %s (primary took %.2fs)", self._server_id, primary_time)
                manager_task = self.client.get_manager_info()
                chassis_task = self.client.get_chassis_info()
                
                # Use appropriate timeout for secondary data (2 concurrent 5-8s calls)
                secondary_timeout = 10.0
                try:
                    manager_data, chassis_data = await asyncio.wait_for(
                        asyncio.gather(manager_task, chassis_task, return_exceptions=True),
                        timeout=secondary_timeout
                    )
                    
                    if isinstance(manager_data, Exception):
                        _LOGGER.debug("Manager data failed: %s", manager_data)
                        manager_data = None
                    if isinstance(chassis_data, Exception):
                        _LOGGER.debug("Chassis data failed: %s", chassis_data)
                        chassis_data = None
                        
                except asyncio.TimeoutError:
                    _LOGGER.warning("Secondary data timeout on %s after %.2fs", self._server_id, secondary_timeout)
                    manager_data = chassis_data = None
                
                # Skip power subsystem for now - it's often slow and non-essential
                power_subsystem_data = None
            else:
                # Skip secondary data if primary took too long or had too many failures
                _LOGGER.debug("Skipping secondary data for %s (primary time: %.2fs, failures: %d)", 
                            self._server_id, primary_time, primary_failures)
                manager_data = chassis_data = power_subsystem_data = None
                
        except asyncio.TimeoutError:
            _LOGGER.warning("Primary data timeout on %s after %.2fs, falling back to individual requests", self._server_id, primary_timeout)
            # Try emergency fallback with individual requests using longer timeout for slow iDRACs
            try:
                system_data = await asyncio.wait_for(self.client.get_system_info(), timeout=8.0)
            except Exception as exc:
                _LOGGER.debug("Individual system request failed: %s", exc)
                system_data = None
            try:
                thermal_data = await asyncio.wait_for(self.client.get_thermal_info(), timeout=8.0)
            except Exception as exc:
                _LOGGER.debug("Individual thermal request failed: %s", exc)
                thermal_data = None
            try:
                power_data = await asyncio.wait_for(self.client.get_power_info(), timeout=8.0)
            except Exception as exc:
                _LOGGER.debug("Individual power request failed: %s", exc)
                power_data = None
            manager_data = chassis_data = power_subsystem_data = None
                
        except Exception as exc:
            _LOGGER.error("Unexpected error during data collection from %s: %s", self._server_id, exc)
            # Set all data to None to continue with partial data processing
            system_data = thermal_data = power_data = manager_data = chassis_data = power_subsystem_data = None

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
                "memory_status": system_data.get("MemorySummary", {}).get("Status", {}).get("Health"),
                "memory_mirroring": system_data.get("MemorySummary", {}).get("MemoryMirroring"),
                "memory_modules_populated": system_data.get("MemorySummary", {}).get("TotalSystemPersistentMemoryGiB"),
                "processor_count": system_data.get("ProcessorSummary", {}).get("Count"),
                "processor_model": system_data.get("ProcessorSummary", {}).get("Model"),
                "processor_status": system_data.get("ProcessorSummary", {}).get("Status", {}).get("Health"),
            }
            
            # Store LED state separately for easy access
            data["indicator_led_state"] = system_data.get("IndicatorLED")

        # Process thermal information
        if thermal_data:
            # Process temperatures - optimize by filtering None readings upfront
            temperatures = [temp for temp in thermal_data.get("Temperatures", []) 
                          if temp.get("ReadingCelsius") is not None]
            for i, temp in enumerate(temperatures):
                sensor_name = temp.get("Name", f"Temperature {i+1}")
                data["temperatures"][f"temp_{i+1}"] = {
                    "name": sensor_name,
                    "temperature": temp.get("ReadingCelsius"),
                    "status": temp.get("Status", {}).get("Health"),
                    "upper_threshold_critical": temp.get("UpperThresholdCritical"),
                    "upper_threshold_non_critical": temp.get("UpperThresholdNonCritical"),
                }

            # Process fans - optimize by filtering None readings upfront
            fans = [fan for fan in thermal_data.get("Fans", []) 
                   if fan.get("Reading") is not None]
            for i, fan in enumerate(fans):
                fan_name = fan.get("Name", f"Fan {i+1}")
                data["fans"][f"fan_{i+1}"] = {
                    "name": fan_name,
                    "speed_rpm": fan.get("Reading"),
                    "speed_percent": fan.get("ReadingUnits") == "Percent" and fan.get("Reading"),
                    "status": fan.get("Status", {}).get("Health"),
                }

        # Process power information
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

        # Process manager information
        if manager_data:
            data["manager_info"] = {
                "name": manager_data.get("Name"),
                "firmware_version": manager_data.get("FirmwareVersion"),
                "model": manager_data.get("Model"),
                "status": manager_data.get("Status", {}).get("Health"),
                "state": manager_data.get("Status", {}).get("State"),
                "datetime": manager_data.get("DateTime"),
            }

        # Process chassis information
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
        else:
            # Ensure chassis_intrusion data exists even if chassis data is not available
            data["chassis_intrusion"] = {
                "status": "Unknown",
                "sensor_number": None,
                "re_arm": None,
            }

        # Process power subsystem for redundancy info
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
        else:
            # Fallback power redundancy calculation when power subsystem unavailable
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
            elif any(health in ["Warning", "warning"] for health in health_components):
                overall_health = "Warning"
            elif all(health in ["OK", "ok"] for health in health_components):
                overall_health = "OK"
            else:
                overall_health = "Unknown"
        else:
            overall_health = "Unknown"
        
        data["system_health"] = {
            "overall_status": overall_health,
            "component_count": len(health_components),
            "components": health_components,
        }

        # Log timing for performance monitoring
        total_time = time.time() - start_time
        if total_time > 15:
            _LOGGER.warning("Redfish update took %.2f seconds - consider optimizing", total_time)
        elif total_time > 10:
            _LOGGER.info("Redfish update completed in %.2f seconds (acceptable for this iDRAC)", total_time)
        else:
            _LOGGER.debug("Redfish update completed in %.2f seconds", total_time)
        
        return data

    async def reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset system via Redfish API."""
        try:
            result = await self.client.reset_system(reset_type)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to reset system on %s: %s", self._server_id, exc)
            return False

    async def set_indicator_led(self, state: str) -> bool:
        """Set indicator LED state via Redfish API."""
        try:
            result = await self.client.set_indicator_led(state)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to set LED on %s: %s", self._server_id, exc)
            return False

    async def close(self) -> None:
        """Close the coordinator."""
        if self.client:
            await self.client.close()