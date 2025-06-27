#!/usr/bin/env python3
"""Test script to verify iDRAC SNMP implementation.

This script tests the SNMP client functionality by:
1. Testing basic SNMP connectivity
2. Checking device information retrieval
3. Testing sensor data collection
4. Validating discovered sensor indices
5. Performing OID walkthrough for troubleshooting
"""

import asyncio
import logging
import sys
from typing import Any, Dict

# Configure logging to see debug information
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress pysnmp debug logs to reduce noise
logging.getLogger('pysnmp').setLevel(logging.WARNING)

try:
    # Import the SNMP client and constants
    from custom_components.idrac.snmp.snmp_client import SNMPClient
    from custom_components.idrac.const import IDRAC_OIDS, SNMP_WALK_OIDS
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import CONF_HOST, CONF_USERNAME
    from custom_components.idrac.const import (
        CONF_COMMUNITY, CONF_SNMP_VERSION, CONF_SNMP_PORT,
        CONF_DISCOVERED_CPUS, CONF_DISCOVERED_FANS, CONF_DISCOVERED_PSUS,
        CONF_DISCOVERED_VOLTAGE_PROBES, CONF_DISCOVERED_MEMORY,
        DEFAULT_SNMP_VERSION, DEFAULT_SNMP_PORT
    )
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Make sure you're running this from the integration directory")
    sys.exit(1)


class MockConfigEntry:
    """Mock configuration entry for testing."""
    
    def __init__(self, host: str, **kwargs):
        self.data = {
            CONF_HOST: host,
            CONF_SNMP_VERSION: kwargs.get('snmp_version', DEFAULT_SNMP_VERSION),
            CONF_COMMUNITY: kwargs.get('community', 'public'),
            CONF_SNMP_PORT: kwargs.get('snmp_port', DEFAULT_SNMP_PORT),
            # Add some example discovered sensors for testing
            CONF_DISCOVERED_CPUS: kwargs.get('discovered_cpus', [1, 2]),
            CONF_DISCOVERED_FANS: kwargs.get('discovered_fans', [1, 2, 3]),
            CONF_DISCOVERED_PSUS: kwargs.get('discovered_psus', [1, 2]),
            CONF_DISCOVERED_VOLTAGE_PROBES: kwargs.get('discovered_voltage_probes', [1, 2]),
            CONF_DISCOVERED_MEMORY: kwargs.get('discovered_memory', [1, 2, 3, 4]),
        }
        if 'username' in kwargs:
            self.data[CONF_USERNAME] = kwargs['username']


async def test_basic_connectivity(client: SNMPClient) -> bool:
    """Test basic SNMP connectivity."""
    print("\n=== Testing Basic SNMP Connectivity ===")
    
    try:
        # Test basic system information OID
        system_name_oid = "1.3.6.1.2.1.1.5.0"  # sysName
        result = await client.get_string(system_name_oid)
        
        if result:
            print(f"✓ SNMP connectivity successful")
            print(f"  System Name: {result}")
            return True
        else:
            print("✗ SNMP connectivity failed - no response")
            return False
            
    except Exception as e:
        print(f"✗ SNMP connectivity failed: {e}")
        return False


async def test_device_info(client: SNMPClient) -> bool:
    """Test device information retrieval."""
    print("\n=== Testing Device Information ===")
    
    try:
        device_info = await client.get_device_info()
        
        if device_info:
            print("✓ Device information retrieved successfully:")
            for key, value in device_info.items():
                print(f"  {key}: {value}")
            return True
        else:
            print("✗ No device information retrieved")
            return False
            
    except Exception as e:
        print(f"✗ Device information retrieval failed: {e}")
        return False


async def test_individual_oids(client: SNMPClient) -> Dict[str, Any]:
    """Test individual OID queries to identify which ones work."""
    print("\n=== Testing Individual OIDs ===")
    
    test_oids = {
        "System Model": IDRAC_OIDS["system_model"],
        "System Service Tag": IDRAC_OIDS["system_service_tag"],
        "System BIOS Version": IDRAC_OIDS["system_bios_version"],
        "Temp Probe 1 Reading": IDRAC_OIDS["temp_probe_reading"].format(index=1),
        "Temp Probe 1 Location": IDRAC_OIDS["temp_probe_location"].format(index=1),
        "Fan 1 Reading": IDRAC_OIDS["cooling_device_reading"].format(index=1),
        "Fan 1 Location": IDRAC_OIDS["cooling_device_location"].format(index=1),
        "PSU 1 Status": IDRAC_OIDS["psu_status"].format(index=1),
        "PSU 1 Location": IDRAC_OIDS["psu_location"].format(index=1)
    }
    
    results = {}
    
    for name, oid in test_oids.items():
        try:
            # Try as string first
            result = await client.get_string(oid)
            if result:
                results[name] = result
                print(f"✓ {name}: {result}")
            else:
                # Try as integer if string fails
                result = await client.get_value(oid)
                if result is not None:
                    results[name] = result
                    print(f"✓ {name}: {result}")
                else:
                    print(f"✗ {name}: No response")
        except Exception as e:
            print(f"✗ {name}: {e}")
    
    return results


async def test_sensor_data_collection(client: SNMPClient) -> bool:
    """Test complete sensor data collection."""
    print("\n=== Testing Sensor Data Collection ===")
    
    try:
        sensor_data = await client.get_sensor_data()
        
        if sensor_data:
            print("✓ Sensor data collected successfully:")
            
            # Check each sensor category
            for category, data in sensor_data.items():
                if data:
                    print(f"  {category}: {len(data)} sensors")
                    for sensor_id, sensor_info in data.items():
                        if isinstance(sensor_info, dict):
                            print(f"    {sensor_id}: {sensor_info.get('name', 'Unknown')}")
                        else:
                            print(f"    {sensor_id}: {sensor_info}")
                else:
                    print(f"  {category}: No data")
            
            return True
        else:
            print("✗ No sensor data collected")
            return False
            
    except Exception as e:
        print(f"✗ Sensor data collection failed: {e}")
        return False


async def test_bulk_operations(client: SNMPClient) -> bool:
    """Test bulk SNMP operations."""
    print("\n=== Testing Bulk Operations ===")
    
    try:
        # Test bulk value retrieval
        value_oids = [
            IDRAC_OIDS["temp_probe_reading"].format(index=1),
            IDRAC_OIDS["temp_probe_status"].format(index=1),
            IDRAC_OIDS["cooling_device_reading"].format(index=1),
        ]
        
        values = await client._bulk_get_values(value_oids)
        
        if values:
            print("✓ Bulk value operations working:")
            for oid, value in values.items():
                print(f"  {oid}: {value}")
        else:
            print("✗ Bulk value operations failed")
            
        # Test bulk string retrieval
        string_oids = [
            IDRAC_OIDS["temp_probe_location"].format(index=1),
            IDRAC_OIDS["cooling_device_location"].format(index=1),
        ]
        
        strings = await client._bulk_get_strings(string_oids)
        
        if strings:
            print("✓ Bulk string operations working:")
            for oid, string in strings.items():
                print(f"  {oid}: {string}")
            return True
        else:
            print("✗ Bulk string operations failed")
            return False
            
    except Exception as e:
        print(f"✗ Bulk operations failed: {e}")
        return False


async def snmp_walk_test(client: SNMPClient) -> None:
    """Perform SNMP walk on key OID branches to discover available sensors."""
    print("\n=== SNMP Walk Test (Discovery) ===")
    
    try:
        from pysnmp.hlapi import getCmd as sync_getCmd, nextCmd as sync_nextCmd
        from pysnmp.hlapi import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        from custom_components.idrac.snmp.snmp_client import _create_auth_data
        
        # Use synchronous SNMP for walking
        sync_engine = SnmpEngine()
        sync_auth = _create_auth_data(client.entry)
        sync_target = UdpTransportTarget((client.host, client.snmp_port), timeout=3, retries=1)
        sync_context = ContextData()
        
        walk_oids = {
            "Temperature Probes": SNMP_WALK_OIDS["temp_probes"],
            "Cooling Devices": SNMP_WALK_OIDS["cooling_devices"],
            "Power Supplies": SNMP_WALK_OIDS["power_supplies"],
            "Memory Devices": SNMP_WALK_OIDS["memory_devices"],
        }
        
        for name, base_oid in walk_oids.items():
            print(f"\nWalking {name} ({base_oid}):")
            
            found_count = 0
            try:
                for (error_indication, error_status, error_index, var_binds) in sync_nextCmd(
                    sync_engine, sync_auth, sync_target, sync_context,
                    ObjectType(ObjectIdentity(base_oid)),
                    lexicographicMode=False, maxRows=10
                ):
                    
                    if error_indication:
                        print(f"  Error: {error_indication}")
                        break
                        
                    if error_status:
                        print(f"  Error: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
                        break
                        
                    for var_bind in var_binds:
                        oid, value = var_bind
                        oid_str = str(oid)
                        
                        if not oid_str.startswith(base_oid):
                            break
                            
                        found_count += 1
                        print(f"  {oid_str}: {value}")
                        
                        if found_count >= 10:  # Limit output
                            print("  ... (truncated)")
                            break
                    
                    if found_count >= 10:
                        break
                        
            except Exception as e:
                print(f"  Walk failed: {e}")
                
            if found_count == 0:
                print("  No entries found")
                
    except Exception as e:
        print(f"SNMP walk failed: {e}")


async def main():
    """Main test function."""
    print("iDRAC SNMP Integration Test")
    print("=" * 40)
    
    # Get host from command line or use default
    host = sys.argv[1] if len(sys.argv) > 1 else input("Enter iDRAC host/IP: ").strip()
    
    if not host:
        print("No host provided. Exiting.")
        return
    
    # Get SNMP community (default: public)
    community = input("Enter SNMP community (default: public): ").strip() or "public"
    
    # Create mock config entry
    config_entry = MockConfigEntry(host=host, community=community)
    
    # Create SNMP client
    client = SNMPClient(config_entry)
    
    print(f"\nTesting SNMP connection to: {host}")
    print(f"Community: {community}")
    print(f"SNMP Version: {client.snmp_version}")
    print(f"SNMP Port: {client.snmp_port}")
    
    # Run tests
    tests_passed = 0
    total_tests = 5
    
    if await test_basic_connectivity(client):
        tests_passed += 1
    
    if await test_device_info(client):
        tests_passed += 1
    
    # Test individual OIDs
    individual_results = await test_individual_oids(client)
    if individual_results:
        tests_passed += 1
    
    if await test_bulk_operations(client):
        tests_passed += 1
    
    if await test_sensor_data_collection(client):
        tests_passed += 1
    
    # Discovery walk (informational only)
    await snmp_walk_test(client)
    
    # Summary
    print(f"\n{'='*40}")
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✓ All tests passed! SNMP implementation appears to be working correctly.")
    elif tests_passed > 0:
        print(f"⚠ Partial success. {total_tests - tests_passed} tests failed.")
        print("Check the output above for specific issues.")
    else:
        print("✗ All tests failed. Check SNMP configuration and network connectivity.")
    
    print("\nTroubleshooting tips:")
    print("1. Verify iDRAC SNMP is enabled and configured")
    print("2. Check SNMP community string")
    print("3. Ensure firewall allows SNMP traffic (UDP 161)")
    print("4. Verify network connectivity to iDRAC")
    print("5. Check if sensors are discovered correctly in Home Assistant")


if __name__ == "__main__":
    asyncio.run(main())