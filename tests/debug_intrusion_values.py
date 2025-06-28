#!/usr/bin/env python3
"""
Purpose: Debug script to understand intrusion sensor values and interpretation
Usage: python tests/debug_intrusion_values.py (uses .env.local or .env.test)
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

# Intrusion sensor OIDs
INTRUSION_OIDS = {
    "location": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1",
    "reading": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1", 
    "status": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1",
}

# Dell intrusion status mapping
INTRUSION_STATUS = {
    1: "breach",
    2: "no_breach", 
    3: "ok",
    4: "unknown"
}

async def debug_intrusion_values(host: str, community: str = "public", port: int = 161):
    """Debug intrusion sensor values to understand status interpretation."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nDebug intrusion sensor values on {host}:{port}")
    print("=" * 80)
    
    print("\nDell iDRAC Intrusion Status Mapping:")
    for code, status in INTRUSION_STATUS.items():
        print(f"  {code} = {status}")
    print()
    
    # Test indices 1-5 for intrusion sensors
    found_sensors = []
    
    for index in range(1, 6):
        print(f"Testing intrusion sensor index {index}:")
        sensor_data = {}
        
        for oid_name, base_oid in INTRUSION_OIDS.items():
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
            
            # Analyze the values
            print("  Analysis:")
            
            # Check reading value (what binary sensor uses)
            if 'reading' in sensor_data:
                try:
                    reading_int = int(sensor_data['reading'])
                    status_text = INTRUSION_STATUS.get(reading_int, "unknown")
                    binary_result = "SAFE" if reading_int in [2, 3] else ("UNSAFE" if reading_int == 1 else "UNKNOWN")
                    print(f"    reading value {reading_int} = '{status_text}' -> Binary sensor shows: {binary_result}")
                except ValueError:
                    print(f"    reading value '{sensor_data['reading']}' is not numeric")
            
            # Check status value (alternative)
            if 'status' in sensor_data:
                try:
                    status_int = int(sensor_data['status'])
                    status_text = INTRUSION_STATUS.get(status_int, "unknown")
                    print(f"    status value {status_int} = '{status_text}'")
                except ValueError:
                    print(f"    status value '{sensor_data['status']}' is not numeric")
                    
            print()
    
    # Summary
    print("Summary:")
    if found_sensors:
        print(f"Found {len(found_sensors)} intrusion sensors:")
        for index, data in found_sensors:
            location = data.get('location', f'Sensor {index}')
            reading = data.get('reading', 'N/A')
            print(f"  {location}: reading={reading}")
            
        print("\nIf your binary sensor shows 'Unsafe' but iDRAC shows 'OK':")
        print("1. Check which 'reading' value corresponds to your problem sensor")
        print("2. If reading=3, binary sensor should show SAFE")
        print("3. If reading=1, binary sensor should show UNSAFE") 
        print("4. If reading=2, binary sensor should show SAFE")
        print("5. Check Home Assistant logs for the sensor's debug output")
    else:
        print("No intrusion sensors found")
    
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
        print("  1. Command line: python tests/debug_intrusion_values.py <host> [community] [port]")
        print("  2. Environment: Configure IDRAC_HOST in .env.local or .env.test")
        sys.exit(1)
    
    print(f"Debug intrusion values on {HOST}:{PORT} with community '{COMMUNITY}'")
    print(f"Usage: {sys.argv[0]} [host] [community] [port]")
    
    asyncio.run(debug_intrusion_values(HOST, COMMUNITY, PORT))