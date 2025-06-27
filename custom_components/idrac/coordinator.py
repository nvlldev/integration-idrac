"""DataUpdateCoordinator for Dell iDRAC."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .redfish_client import RedfishClient, RedfishError

_LOGGER = logging.getLogger(__name__)


class IdracDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Dell iDRAC via Redfish API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.port = entry.data.get(CONF_PORT, 443)
        self.verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
        
        # Create Redfish client
        self.client = RedfishClient(
            hass, self.host, self.username, self.password, self.port, self.verify_ssl
        )
        
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
            "configuration_url": f"https://{self.host}",
        }
        
        # Get system information
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

    @property 
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info or {
            "identifiers": {(DOMAIN, self._server_id)},
            "name": f"Dell iDRAC ({self.host})",
            "manufacturer": "Dell",
            "model": "iDRAC",
            "configuration_url": f"https://{self.host}",
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via Redfish API."""
        try:
            # Fetch device info on first run
            if self._device_info is None:
                await self._async_fetch_device_info()
            
            data = {
                "temperatures": {},
                "fans": {},
                "power_supplies": {},
                "voltages": {},
                "system_info": {},
                "manager_info": {},
            }

            # Get system information
            system_data = await self.client.get_system_info()
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

            # Get thermal information
            thermal_data = await self.client.get_thermal_info()
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

            # Get power information
            power_data = await self.client.get_power_info()
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

            # Get manager information
            manager_data = await self.client.get_manager_info()
            if manager_data:
                data["manager_info"] = {
                    "name": manager_data.get("Name"),
                    "firmware_version": manager_data.get("FirmwareVersion"),
                    "model": manager_data.get("Model"),
                    "status": manager_data.get("Status", {}).get("Health"),
                    "state": manager_data.get("Status", {}).get("State"),
                    "datetime": manager_data.get("DateTime"),
                }

            return data

        except RedfishError as exc:
            raise UpdateFailed(f"Authentication failed for iDRAC {self._server_id}: {exc}") from exc
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with iDRAC {self._server_id}: {exc}") from exc

    async def async_reset_system(self, reset_type: str = "GracefulRestart") -> bool:
        """Reset system via Redfish API."""
        try:
            result = await self.client.reset_system(reset_type)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to reset system on %s: %s", self._server_id, exc)
            return False

    async def async_set_indicator_led(self, state: str) -> bool:
        """Set indicator LED state via Redfish API."""
        try:
            result = await self.client.set_indicator_led(state)
            return result is not None
        except Exception as exc:
            _LOGGER.error("Failed to set LED on %s: %s", self._server_id, exc)
            return False