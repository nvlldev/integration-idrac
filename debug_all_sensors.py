#!/usr/bin/env python3
"""Debug script to show ALL voltage-related sensors being created."""

import asyncio
import sys
from pathlib import Path

# Add the custom_components directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "custom_components"))

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT

# Mock Home Assistant for testing
class MockHass:
    pass

# Mock config entry
class MockConfigEntry:
    def __init__(self):
        self.data = {
            CONF_HOST: "192.168.50.131",
            CONF_PORT: 443,
            "username": "root",
            "password": "calvin"
        }

async def test_sensor_creation():
    """Test what sensors get created."""
    print("=" * 80)
    print("TESTING SENSOR CREATION")
    print("=" * 80)
    
    try:
        from idrac.redfish.redfish_coordinator import RedfishCoordinator
        from idrac.snmp.snmp_coordinator import SNMPCoordinator
        
        # Create coordinators
        config_entry = MockConfigEntry()
        hass = MockHass()
        
        redfish_coordinator = RedfishCoordinator(hass, config_entry)
        snmp_coordinator = SNMPCoordinator(hass, config_entry)
        
        # Refresh data
        await redfish_coordinator.async_refresh()
        await snmp_coordinator.async_refresh()
        
        print("\nREDFISH COORDINATOR DATA:")
        if redfish_coordinator.data and "voltages" in redfish_coordinator.data:
            voltages = redfish_coordinator.data["voltages"]
            print(f"Found {len(voltages)} voltage sensors in Redfish:")
            for voltage_id, voltage_data in voltages.items():
                name = voltage_data.get("name", "Unknown")
                value = voltage_data.get("reading_volts", "N/A")
                source = voltage_data.get("source", "unknown")
                print(f"  {voltage_id}: {name} = {value}V (source: {source})")
        
        if redfish_coordinator.data and "system_voltages" in redfish_coordinator.data:
            system_voltages = redfish_coordinator.data["system_voltages"] 
            print(f"\nFound {len(system_voltages)} system voltage sensors in Redfish:")
            for voltage_id, voltage_data in system_voltages.items():
                name = voltage_data.get("name", "Unknown")
                reading = voltage_data.get("reading", "N/A")
                voltage_value = voltage_data.get("voltage_value", "N/A")
                print(f"  {voltage_id}: {name} = reading:{reading} voltage:{voltage_value}V")
        
        print("\nSNMP COORDINATOR DATA:")
        if snmp_coordinator.data and "voltages" in snmp_coordinator.data:
            voltages = snmp_coordinator.data["voltages"]
            print(f"Found {len(voltages)} voltage sensors in SNMP:")
            for voltage_id, voltage_data in voltages.items():
                name = voltage_data.get("name", "Unknown")
                value = voltage_data.get("reading_volts", "N/A")
                print(f"  {voltage_id}: {name} = {value}V")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sensor_creation())