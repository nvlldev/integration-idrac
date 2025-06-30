#!/usr/bin/env python3
"""Simple debug script to examine voltage sensor data from iDRAC APIs."""

import asyncio
import json
import sys
from pathlib import Path

# Add the custom_components directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "custom_components"))

from idrac.redfish.redfish_api import RedfishAPI
from idrac.snmp.snmp_client import SNMPClient

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
        redfish_api = RedfishAPI(IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD, IDRAC_PORT)
        
        # Get chassis data which contains power/voltage info
        chassis_data = await redfish_api.get_chassis()
        
        if chassis_data and "Power" in chassis_data:
            power_data = chassis_data["Power"]
            
            # Check PowerSupplies data
            power_supplies = power_data.get("PowerSupplies", [])
            print(f"\nPowerSupplies data ({len(power_supplies)} entries):")
            for i, psu in enumerate(power_supplies):
                name = psu.get("Name", f"PSU {i+1}")
                voltage = psu.get("LineInputVoltage")
                print(f"  [{i}] {name}: LineInputVoltage = {voltage}V")
            
            # Check Voltages array
            voltages = power_data.get("Voltages", [])
            print(f"\nVoltages array ({len(voltages)} entries):")
            for i, voltage in enumerate(voltages):
                name = voltage.get("Name", f"Voltage {i+1}")
                value = voltage.get("ReadingVolts")
                
                # Highlight sensors with values around 12V and 2V
                highlight = ""
                if isinstance(value, (int, float)):
                    if 10 <= value <= 14:
                        highlight = " <-- ~12V (POTENTIAL REMOVAL TARGET)"
                    elif 1 <= value <= 3:
                        highlight = " <-- ~2V (POTENTIAL REMOVAL TARGET)"
                    elif 110 <= value <= 130:
                        highlight = " <-- ~120V (GOOD PSU INPUT VOLTAGE)"
                
                print(f"  [{i}] {name} = {value}V{highlight}")
        
        await redfish_api.close()
        
    except Exception as e:
        print(f"Error with Redfish API: {e}")
        import traceback
        traceback.print_exc()
    
    # Test SNMP voltage data
    print("\n" + "=" * 40)
    print("SNMP VOLTAGE DATA")
    print("=" * 40)
    
    try:
        snmp_client = SNMPClient(IDRAC_HOST, 161, "public")
        
        # Get voltage probe data
        voltage_data = await snmp_client.get_voltage_data()
        
        if voltage_data:
            print(f"\nFound {len(voltage_data)} voltage sensors from SNMP:")
            for voltage_id, data in voltage_data.items():
                name = data.get("name", "Unknown")
                value = data.get("reading_volts", "N/A")
                
                # Highlight sensors with values around 12V and 2V
                highlight = ""
                if isinstance(value, (int, float)):
                    if 10 <= value <= 14:
                        highlight = " <-- ~12V (POTENTIAL REMOVAL TARGET)"
                    elif 1 <= value <= 3:
                        highlight = " <-- ~2V (POTENTIAL REMOVAL TARGET)"
                    elif 110 <= value <= 130:
                        highlight = " <-- ~120V (GOOD PSU INPUT VOLTAGE)"
                
                print(f"  {voltage_id}: {name} = {value}V{highlight}")
        else:
            print("No voltage data found from SNMP")
            
    except Exception as e:
        print(f"Error with SNMP client: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Look for voltage sensors marked with 'POTENTIAL REMOVAL TARGET'")
    print("These are the sensors with values around 12V and 2V that should be filtered out.")
    print("The good PSU input voltage sensors should be around 118-124V (marked as 'GOOD').")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_voltage_sensors())