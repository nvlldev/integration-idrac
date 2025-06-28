#!/usr/bin/env python3
"""
Purpose: Debug script to identify unwanted voltage sensors
Usage: python tests/debug_voltage_sensors.py (uses .env.local or .env.test)
Requirements: python-dotenv, pysnmp
Author: Claude Code Assistant
Date: 2025-01-28
"""
import asyncio
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    # Load environment variables (.env.local preferred, .env.test fallback)
    load_dotenv('.env.local')
    load_dotenv('.env.test')
except ImportError:
    print("Warning: python-dotenv not installed. Using command line arguments only.")
    load_dotenv = None

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Voltage sensor OIDs
VOLTAGE_OIDS = {
    "location": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1",
    "reading": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
}

async def debug_voltage_sensors(host: str, community: str = "public", port: int = 161):
    """Debug voltage sensors to identify unwanted ones."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nDebug voltage sensors on {host}:{port}")
    print("=" * 80)
    
    # Test indices 1-10 for voltage sensors
    found_sensors = []
    
    for index in range(1, 11):
        print(f"\nTesting voltage sensor index {index}:")
        sensor_data = {}
        
        for oid_name, base_oid in VOLTAGE_OIDS.items():
            test_oid = f"{base_oid}.{index}"
            
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    for name, val in var_binds:
                        if val is not None and str(val) != "No Such Object currently exists at this OID":
                            sensor_data[oid_name] = str(val)
                            print(f"  {oid_name}: {val}")
                        else:
                            print(f"  {oid_name}: No object")
                            
            except Exception as exc:
                print(f"  {oid_name}: Exception - {exc}")
        
        if sensor_data:
            found_sensors.append((index, sensor_data))
            
            # Analysis
            location = sensor_data.get('location', 'No location')
            reading = sensor_data.get('reading', 'No reading')
            
            print(f"  Analysis:")
            print(f"    Location: '{location}'")
            
            # Check if this would be filtered
            would_be_filtered = False
            filter_reason = ""
            
            # PSU filter check
            if location and any(psu_term in location.lower() for psu_term in ["ps1", "ps2", "ps3", "psu"]):
                would_be_filtered = True
                filter_reason = "PSU voltage sensor"
            
            # Power consumption filter check
            elif location and any(power_term in location.lower() for power_term in ["pwr consumption", "power consumption", "consumption", "board pwr consumption"]):
                would_be_filtered = True
                filter_reason = "Power consumption sensor"
            
            # Empty location filter check
            elif not location or location.strip() == "" or location.strip() == "No location":
                would_be_filtered = True
                filter_reason = "No meaningful location name"
            
            if would_be_filtered:
                print(f"    Status: FILTERED OUT ({filter_reason})")
            else:
                print(f"    Status: WOULD APPEAR in Home Assistant as '{location} Voltage'")
                if index == 3:
                    print(f"    *** This is likely your 'Voltage 3' sensor! ***")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"Found {len(found_sensors)} voltage sensors")
    
    filtered_sensors = []
    visible_sensors = []
    
    for index, data in found_sensors:
        location = data.get('location', '')
        
        # Apply same filtering logic
        if location and any(psu_term in location.lower() for psu_term in ["ps1", "ps2", "ps3", "psu"]):
            filtered_sensors.append(f"Index {index}: {location} (PSU filter)")
        elif location and any(power_term in location.lower() for power_term in ["pwr consumption", "power consumption", "consumption", "board pwr consumption"]):
            filtered_sensors.append(f"Index {index}: {location} (Power consumption filter)")
        elif not location or location.strip() == "":
            filtered_sensors.append(f"Index {index}: No location (empty filter)")
        else:
            visible_sensors.append(f"Index {index}: {location}")
    
    print(f"\nSensors that will be FILTERED OUT:")
    for sensor in filtered_sensors:
        print(f"  - {sensor}")
    
    print(f"\nSensors that will APPEAR in Home Assistant:")
    for sensor in visible_sensors:
        print(f"  - {sensor}")
        
    if any("Index 3:" in sensor for sensor in visible_sensors):
        print(f"\n*** SOLUTION for 'Voltage 3': ***")
        voltage_3_sensor = next(sensor for sensor in visible_sensors if "Index 3:" in sensor)
        location_name = voltage_3_sensor.split(": ", 1)[1]
        print(f"Your 'Voltage 3' sensor has location: '{location_name}'")
        print(f"We can add this to the filter to remove it.")
    
    engine.close()

if __name__ == "__main__":
    # Get configuration from environment files or command line
    if len(sys.argv) > 1:
        HOST = sys.argv[1]
        COMMUNITY = sys.argv[2] if len(sys.argv) > 2 else "public"
        PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 161
    else:
        # Get from environment variables
        HOST = os.getenv('IDRAC_HOST')
        COMMUNITY = os.getenv('IDRAC_COMMUNITY', 'public')
        PORT = int(os.getenv('IDRAC_PORT', '161'))
    
    if not HOST:
        print("Error: Please provide iDRAC host via:")
        print("  1. Command line: python tests/debug_voltage_sensors.py <host> [community] [port]")
        print("  2. Environment: Configure IDRAC_HOST in .env.local or .env.test")
        sys.exit(1)
    
    print(f"Debug voltage sensors on {HOST}:{PORT} with community '{COMMUNITY}'")
    print(f"Usage: {sys.argv[0]} [host] [community] [port]")
    
    asyncio.run(debug_voltage_sensors(HOST, COMMUNITY, PORT))