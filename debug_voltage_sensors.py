#!/usr/bin/env python3
"""Debug script to examine voltage sensor data from iDRAC APIs."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the custom_components directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "custom_components"))

from idrac.redfish.redfish_coordinator import RedfishCoordinator
from idrac.snmp.snmp_coordinator import SNMPCoordinator

# Configure logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# iDRAC connection settings
IDRAC_HOST = "192.168.50.131"
IDRAC_PORT = 443
IDRAC_USERNAME = "root"
IDRAC_PASSWORD = "calvin"

async def debug_voltage_sensors():
    """Debug voltage sensors from both Redfish and SNMP."""
    
    print("=" * 80)
    print("VOLTAGE SENSOR DEBUG SCRIPT")
    print("=" * 80)
    
    # Test Redfish voltage data
    print("\n" + "=" * 40)
    print("REDFISH VOLTAGE DATA")
    print("=" * 40)
    
    try:
        redfish_coordinator = RedfishCoordinator(
            IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD, IDRAC_PORT
        )
        
        await redfish_coordinator.async_refresh()
        
        if redfish_coordinator.data and "voltages" in redfish_coordinator.data:
            voltages = redfish_coordinator.data["voltages"]
            print(f"\nFound {len(voltages)} voltage sensors from Redfish:")
            
            for voltage_id, voltage_data in voltages.items():
                name = voltage_data.get("name", "Unknown")
                value = voltage_data.get("reading_volts", "N/A")
                source = voltage_data.get("source", "unknown")
                status = voltage_data.get("status", "unknown")
                
                # Highlight sensors with values around 12V and 2V
                highlight = ""
                if isinstance(value, (int, float)):
                    if 10 <= value <= 14:
                        highlight = " <-- ~12V (POTENTIAL REMOVAL TARGET)"
                    elif 1 <= value <= 3:
                        highlight = " <-- ~2V (POTENTIAL REMOVAL TARGET)"
                
                print(f"  {voltage_id}: {name} = {value}V (source: {source}, status: {status}){highlight}")
        else:
            print("No voltage data found in Redfish coordinator")
            
        # Also check raw Redfish voltage data
        if hasattr(redfish_coordinator, 'api_client'):
            print("\n" + "-" * 40)
            print("RAW REDFISH VOLTAGES ARRAY")
            print("-" * 40)
            
            try:
                chassis_data = await redfish_coordinator.api_client.get_chassis()
                if chassis_data:
                    power_data = chassis_data.get("Power", {})
                    raw_voltages = power_data.get("Voltages", [])
                    
                    print(f"Found {len(raw_voltages)} raw voltage sensors:")
                    for i, voltage in enumerate(raw_voltages):
                        name = voltage.get("Name", f"Voltage {i+1}")
                        value = voltage.get("ReadingVolts")
                        
                        highlight = ""
                        if isinstance(value, (int, float)):
                            if 10 <= value <= 14:
                                highlight = " <-- ~12V (POTENTIAL REMOVAL TARGET)"
                            elif 1 <= value <= 3:
                                highlight = " <-- ~2V (POTENTIAL REMOVAL TARGET)"
                        
                        print(f"  [{i}] {name} = {value}V{highlight}")
                        
            except Exception as e:
                print(f"Error getting raw Redfish data: {e}")
                
    except Exception as e:
        print(f"Error with Redfish coordinator: {e}")
    
    # Test SNMP voltage data
    print("\n" + "=" * 40)
    print("SNMP VOLTAGE DATA")
    print("=" * 40)
    
    try:
        snmp_coordinator = SNMPCoordinator(
            IDRAC_HOST, 161, "public"
        )
        
        await snmp_coordinator.async_refresh()
        
        if snmp_coordinator.data and "voltages" in snmp_coordinator.data:
            voltages = snmp_coordinator.data["voltages"]
            print(f"\nFound {len(voltages)} voltage sensors from SNMP:")
            
            for voltage_id, voltage_data in voltages.items():
                name = voltage_data.get("name", "Unknown")
                value = voltage_data.get("reading_volts", "N/A")
                
                # Highlight sensors with values around 12V and 2V
                highlight = ""
                if isinstance(value, (int, float)):
                    if 10 <= value <= 14:
                        highlight = " <-- ~12V (POTENTIAL REMOVAL TARGET)"
                    elif 1 <= value <= 3:
                        highlight = " <-- ~2V (POTENTIAL REMOVAL TARGET)"
                
                print(f"  {voltage_id}: {name} = {value}V{highlight}")
        else:
            print("No voltage data found in SNMP coordinator")
            
    except Exception as e:
        print(f"Error with SNMP coordinator: {e}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Look for voltage sensors marked with 'POTENTIAL REMOVAL TARGET'")
    print("These are the sensors with values around 12V and 2V that should be filtered out.")
    print("The good PSU input voltage sensors should be around 118-124V.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_voltage_sensors())