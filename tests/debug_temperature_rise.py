#!/usr/bin/env python3
"""
Purpose: Debug script to diagnose Temperature Rise sensor availability
Usage: python tests/debug_temperature_rise.py (uses .env.local or .env.test)
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
    nextCmd,
)

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Temperature sensor OID
TEMP_PROBE_LOCATION_OID = "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1"

async def walk_temperature_sensors(host: str, community: str = "public", port: int = 161):
    """Walk temperature sensor locations to see what's available for Temperature Rise calculation."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nDebug Temperature Rise sensor on {host}:{port}")
    print("=" * 80)
    
    # Walk temperature probe locations
    print("\n1. Walking temperature sensor locations...")
    temp_locations = {}
    
    try:
        async for error_indication, error_status, error_index, var_binds in nextCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(TEMP_PROBE_LOCATION_OID)),
            lexicographicMode=False
        ):
            if error_indication:
                _LOGGER.error("Walk error: %s", error_indication)
                break
            elif error_status:
                _LOGGER.error("Walk error status: %s", error_status.prettyPrint())
                break
            else:
                for var_bind in var_binds:
                    oid = str(var_bind[0])
                    value = str(var_bind[1])
                    # Stop if we've walked past our base OID
                    if not oid.startswith(TEMP_PROBE_LOCATION_OID):
                        break
                    
                    # Extract index from OID
                    index = oid.replace(TEMP_PROBE_LOCATION_OID + ".", "")
                    temp_locations[index] = value
                    print(f"  Index {index}: {value}")
    except Exception as e:
        print(f"Error walking temperature sensors: {e}")
        print("This might be due to SNMP connectivity issues or missing pysnmp dependencies")
    
    if not temp_locations:
        print("  No temperature sensors found")
        engine.close()
        return
    
    print(f"\nFound {len(temp_locations)} temperature sensors")
    
    # Analyze for inlet/outlet patterns
    print("\n2. Analyzing for Temperature Rise sensor requirements...")
    inlet_patterns = ["inlet", "intake", "ambient"]
    outlet_patterns = ["outlet", "exhaust", "exit"]
    
    # Also check for broader temperature patterns that might be suitable
    airflow_patterns = ["system", "board", "cpu", "intake", "exhaust", "front", "rear", "back"]
    
    inlet_sensors = []
    outlet_sensors = []
    
    for index, location in temp_locations.items():
        location_lower = location.lower()
        
        # Check for inlet patterns
        for pattern in inlet_patterns:
            if pattern in location_lower:
                inlet_sensors.append((index, location))
                print(f"  INLET found - Index {index}: {location}")
                break
        
        # Check for outlet patterns  
        for pattern in outlet_patterns:
            if pattern in location_lower:
                outlet_sensors.append((index, location))
                print(f"  OUTLET found - Index {index}: {location}")
                break
    
    # Summary
    print("\n3. Temperature Rise sensor availability:")
    print(f"  - Inlet sensors found: {len(inlet_sensors)}")
    if inlet_sensors:
        for index, location in inlet_sensors:
            print(f"    * Index {index}: {location}")
    
    print(f"  - Outlet sensors found: {len(outlet_sensors)}")
    if outlet_sensors:
        for index, location in outlet_sensors:
            print(f"    * Index {index}: {location}")
    
    if inlet_sensors and outlet_sensors:
        print("  ✅ Temperature Rise sensor SHOULD be available")
        print("  - The integration should create a Temperature Rise sensor")
        print("  - If it's missing, check Home Assistant logs for temperature sensor processing")
    else:
        print("  ❌ Temperature Rise sensor CANNOT be created")
        if not inlet_sensors:
            print("  - No inlet/intake/ambient temperature sensors found")
        if not outlet_sensors:
            print("  - No outlet/exhaust/exit temperature sensors found")
        print("  - Temperature Rise requires both inlet and outlet sensors")
    
    # Check for potential airflow-related sensors
    print("\n4. Potential airflow/thermal sensors:")
    airflow_sensors = []
    for index, location in temp_locations.items():
        location_lower = location.lower()
        for pattern in airflow_patterns:
            if pattern in location_lower:
                airflow_sensors.append((index, location))
                print(f"  AIRFLOW - Index {index}: {location}")
                break
    
    if not airflow_sensors:
        print("  No airflow-related temperature sensors found")
    
    # Show all sensors for reference
    print("\n5. All temperature sensors (for reference):")
    for index, location in sorted(temp_locations.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        print(f"  Index {index}: {location}")
    
    # Recommendations
    print("\n6. Recommendations:")
    if not inlet_sensors and not outlet_sensors:
        print("  - No traditional inlet/outlet sensors found")
        print("  - This is common on many Dell servers")
        print("  - Temperature Rise sensor requires specific inlet/outlet naming")
        
        if airflow_sensors:
            print("  - Consider mapping airflow sensors to inlet/outlet if appropriate:")
            for index, location in airflow_sensors[:2]:  # Show first 2 as examples
                print(f"    * {location} could potentially be used for thermal analysis")
        
        print("  - Alternative: Use individual temperature sensors for monitoring")
        print("  - The Temperature Rise sensor is primarily useful for rack thermal efficiency")
    else:
        print("  - Temperature Rise sensor should be available with found sensors")
    
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
        print("  1. Command line: python tests/debug_temperature_rise.py <host> [community] [port]")
        print("  2. Environment: Configure IDRAC_HOST in .env.local or .env.test")
        sys.exit(1)
    
    print(f"Debug Temperature Rise sensor on {HOST}:{PORT} with community '{COMMUNITY}'")
    print(f"Usage: {sys.argv[0]} [host] [community] [port]")
    
    asyncio.run(walk_temperature_sensors(HOST, COMMUNITY, PORT))