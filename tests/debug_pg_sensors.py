#!/usr/bin/env python3
"""
Purpose: Debug script to identify CPU PG (Power Good) sensors specifically
Usage: python tests/debug_pg_sensors.py (uses .env.local or .env.test)
Requirements: python-dotenv, pysnmp
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

# Voltage sensor OIDs (same as debug_voltage_sensors.py)
VOLTAGE_OIDS = {
    "location": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1",
    "reading": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
}

async def debug_pg_sensors(host: str, community: str = "public", port: int = 161):
    """Debug specifically for CPU PG (Power Good) sensors."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nDebug CPU PG sensors on {host}:{port}")
    print("=" * 80)
    
    # Test indices 1-20 for voltage sensors to catch more PG sensors
    found_sensors = []
    pg_sensors = []
    
    for index in range(1, 21):
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
                            
            except Exception as exc:
                pass  # Skip exceptions for cleaner output
        
        if sensor_data:
            found_sensors.append((index, sensor_data))
            
            location = sensor_data.get('location', '')
            reading = sensor_data.get('reading', '')
            
            # Check if this is a PG sensor
            location_lower = location.lower() if location else ""
            is_pg_sensor = (
                " pg" in location_lower or
                location_lower.endswith(" pg") or
                "power good" in location_lower
            )
            
            if is_pg_sensor:
                pg_sensors.append((index, sensor_data))
                print(f"🔍 FOUND PG SENSOR - Index {index}:")
                print(f"    Location: '{location}'")
                print(f"    Reading: {reading}")
                print(f"    Analysis: This should be a binary diagnostic sensor")
                
                # Test the conversion logic
                try:
                    voltage_reading = int(reading)
                    voltage_volts = voltage_reading / 1000.0 if voltage_reading > 1000 else float(voltage_reading)
                    is_ok = voltage_volts > 0.5
                    clean_name = location.replace(" Voltage", "").replace(" PG", " Power Good")
                    
                    print(f"    Converted Values:")
                    print(f"      Voltage: {voltage_volts}V")
                    print(f"      Status: {'OK' if is_ok else 'NOT OK'}")
                    print(f"      Clean Name: '{clean_name}'")
                    print(f"      Sensor Type: power_good")
                    print(f"      Entity Category: DIAGNOSTIC")
                    print(f"      Device Class: POWER")
                except:
                    print(f"    Conversion Error: Could not convert reading '{reading}'")
                
                print()
    
    # Summary
    print(f"{'='*80}")
    print("SUMMARY:")
    print(f"Found {len(found_sensors)} total voltage sensors")
    print(f"Found {len(pg_sensors)} PG sensors")
    
    if pg_sensors:
        print(f"\nPG SENSORS THAT SHOULD BE IN DIAGNOSTICS:")
        for index, data in pg_sensors:
            location = data.get('location', '')
            print(f"  - Index {index}: {location}")
        
        print(f"\nThese sensors should appear in Home Assistant as:")
        print(f"  - Entity Category: DIAGNOSTIC")
        print(f"  - Device Class: POWER")
        print(f"  - Icon: mdi:cpu-64-bit")
        print(f"  - Default State: Disabled")
        print(f"  - Expected Location: Settings > Devices & Services > iDRAC > Configure > Show disabled")
    else:
        print(f"\nNo PG sensors found. This means:")
        print(f"  - Your iDRAC may not have CPU PG sensors")
        print(f"  - They may be at different indices (>20)")
        print(f"  - They may use different OIDs")
    
    print(f"\nAll voltage sensors found:")
    for index, data in found_sensors:
        location = data.get('location', 'No location')
        print(f"  - Index {index}: {location}")

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
        print("  1. Command line: python tests/debug_pg_sensors.py <host> [community] [port]")
        print("  2. Environment: Configure IDRAC_HOST in .env.local or .env.test")
        sys.exit(1)
    
    asyncio.run(debug_pg_sensors(HOST, COMMUNITY, PORT))