#!/usr/bin/env python3
"""Simple SNMP test script without Home Assistant dependencies.

This script tests basic SNMP functionality using only pysnmp.
"""

import asyncio
import sys
import os
from typing import Any, Dict, Optional

try:
    from pysnmp.hlapi.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        UsmUserData,
        getCmd,
        nextCmd,
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
        usmDESPrivProtocol,
        usmAesCfb128Protocol,
    )
    from pysnmp.proto import rfc1902
except ImportError as e:
    print(f"Failed to import pysnmp: {e}")
    print("Install with: pip install pysnmp")
    sys.exit(1)

def load_env_file():
    """Load environment variables from .env file."""
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        print("No .env file found")
    return env_vars


# Key OIDs for testing
TEST_OIDS = {
    # System information
    "system_name": "1.3.6.1.2.1.1.5.0",
    "system_desc": "1.3.6.1.2.1.1.1.0",
    "system_uptime": "1.3.6.1.2.1.1.3.0",
    
    # Dell iDRAC specific OIDs
    "system_model": "1.3.6.1.4.1.674.10892.5.1.3.12.0",
    "system_service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",
    "system_bios_version": "1.3.6.1.4.1.674.10892.5.1.3.6.0",
    
    # Temperature sensors (with index 1)
    "temp_probe_1_reading": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.1",
    "temp_probe_1_location": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.1",
    "temp_probe_1_status": "1.3.6.1.4.1.674.10892.5.4.700.20.1.5.1.1",
    
    # Fan sensors (with index 1)
    "fan_1_reading": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.1",
    "fan_1_location": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.1",
    "fan_1_status": "1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1.1",
    
    # PSU sensors (with index 1)
    "psu_1_status": "1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1.1",
    "psu_1_location": "1.3.6.1.4.1.674.10892.5.4.600.12.1.7.1.1",
}

# Base OIDs for walking
WALK_OIDS = {
    "temperature_probes": "1.3.6.1.4.1.674.10892.5.4.700.20.1",
    "cooling_devices": "1.3.6.1.4.1.674.10892.5.4.700.12.1",
    "power_supplies": "1.3.6.1.4.1.674.10892.5.4.600.12.1",
    "memory_devices": "1.3.6.1.4.1.674.10892.5.4.1100.50.1",
}

# Status mappings
STATUS_MAPPINGS = {
    1: "other",
    2: "unknown",
    3: "ok",
    4: "non_critical",
    5: "critical",
    6: "non_recoverable",
}


class SimpleSnmpClient:
    """Simple SNMP client for testing."""
    
    def __init__(self, host: str, community: str = "public", port: int = 161, 
                 snmp_version: str = "v2c", username: str = None, 
                 auth_password: str = None, priv_password: str = None):
        self.host = host
        self.community = community
        self.port = port
        self.snmp_version = snmp_version
        self.engine = SnmpEngine()
        
        # Create appropriate auth data based on SNMP version
        if snmp_version == "v3" and username:
            self.auth_data = UsmUserData(
                userName=username,
                authKey=auth_password if auth_password else None,
                privKey=priv_password if priv_password else None,
                authProtocol=usmHMACMD5AuthProtocol if auth_password else None,
                privProtocol=usmDESPrivProtocol if priv_password else None,
            )
        else:
            self.auth_data = CommunityData(community)
            
        self.transport_target = UdpTransportTarget((host, port), timeout=5, retries=2)
        self.context_data = ContextData()
        
    async def get_value(self, oid: str) -> Optional[Any]:
        """Get a single SNMP value."""
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(oid))
            )
            
            if error_indication:
                print(f"SNMP Error: {error_indication}")
                return None
                
            if error_status:
                print(f"SNMP Error: {error_status.prettyPrint()} at {error_index}")
                return None
                
            for name, val in var_binds:
                if str(val) == "No Such Object currently exists at this OID":
                    return None
                return val
                
        except Exception as e:
            print(f"Exception getting {oid}: {e}")
            return None
    
    async def walk_oid(self, base_oid: str, max_results: int = 20) -> Dict[str, Any]:
        """Walk an OID tree."""
        results = {}
        count = 0
        
        try:
            iterator = nextCmd(
                self.engine,
                self.auth_data,
                self.transport_target,
                self.context_data,
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            )
            
            async for (error_indication, error_status, error_index, var_binds) in iterator:
                if error_indication:
                    print(f"Walk Error: {error_indication}")
                    break
                    
                if error_status:
                    print(f"Walk Error: {error_status.prettyPrint()}")
                    break
                    
                for name, val in var_binds:
                    oid_str = str(name)
                    if not oid_str.startswith(base_oid):
                        return results
                        
                    results[oid_str] = val
                    count += 1
                    
                    if count >= max_results:
                        return results
                        
        except Exception as e:
            print(f"Exception walking {base_oid}: {e}")
            
        return results


async def test_basic_connectivity(client: SimpleSnmpClient) -> bool:
    """Test basic SNMP connectivity."""
    print("\n=== Testing Basic SNMP Connectivity ===")
    
    # Test system name
    system_name = await client.get_value(TEST_OIDS["system_name"])
    if system_name:
        print(f"✓ System Name: {system_name}")
        
        # Test system description
        system_desc = await client.get_value(TEST_OIDS["system_desc"])
        if system_desc:
            print(f"✓ System Description: {system_desc}")
            
        return True
    else:
        print("✗ Failed to get system name - SNMP not responding")
        return False


async def test_dell_specific_oids(client: SimpleSnmpClient) -> bool:
    """Test Dell-specific OIDs."""
    print("\n=== Testing Dell iDRAC Specific OIDs ===")
    
    success_count = 0
    
    dell_oids = {
        "System Model": "system_model",
        "Service Tag": "system_service_tag", 
        "BIOS Version": "system_bios_version",
    }
    
    for name, oid_key in dell_oids.items():
        value = await client.get_value(TEST_OIDS[oid_key])
        if value:
            print(f"✓ {name}: {value}")
            success_count += 1
        else:
            print(f"✗ {name}: No response")
    
    return success_count > 0


async def test_sensor_oids(client: SimpleSnmpClient) -> bool:
    """Test sensor-specific OIDs."""
    print("\n=== Testing Sensor OIDs ===")
    
    success_count = 0
    
    sensor_tests = [
        ("Temperature Probe 1 Reading", "temp_probe_1_reading"),
        ("Temperature Probe 1 Location", "temp_probe_1_location"),
        ("Temperature Probe 1 Status", "temp_probe_1_status"),
        ("Fan 1 Reading", "fan_1_reading"),
        ("Fan 1 Location", "fan_1_location"),
        ("Fan 1 Status", "fan_1_status"),
        ("PSU 1 Status", "psu_1_status"),
        ("PSU 1 Location", "psu_1_location"),
    ]
    
    for name, oid_key in sensor_tests:
        value = await client.get_value(TEST_OIDS[oid_key])
        if value is not None:
            # Try to format the value based on type
            if name.endswith("Status"):
                status_text = STATUS_MAPPINGS.get(int(value), f"unknown({value})")
                print(f"✓ {name}: {value} ({status_text})")
            elif name.endswith("Reading") and "Temperature" in name:
                # Temperature readings might be in tenths of degrees
                temp_c = float(value) / 10.0 if int(value) > 100 else float(value)
                print(f"✓ {name}: {value} ({temp_c}°C)")
            else:
                print(f"✓ {name}: {value}")
            success_count += 1
        else:
            print(f"✗ {name}: No response")
    
    return success_count > 0


async def test_snmp_walks(client: SimpleSnmpClient) -> None:
    """Test SNMP walks to discover available sensors."""
    print("\n=== Testing SNMP Walks (Discovery) ===")
    
    for name, base_oid in WALK_OIDS.items():
        print(f"\nWalking {name} ({base_oid}):")
        
        results = await client.walk_oid(base_oid, max_results=10)
        
        if results:
            print(f"  Found {len(results)} entries:")
            for oid, value in list(results.items())[:5]:  # Show first 5
                print(f"    {oid}: {value}")
            if len(results) > 5:
                print(f"    ... and {len(results) - 5} more")
        else:
            print("  No entries found")


async def main():
    """Main test function."""
    print("Simple iDRAC SNMP Test")
    print("=" * 30)
    
    # Load configuration from .env file
    env_vars = load_env_file()
    
    # Get connection details from .env or prompt
    host = env_vars.get('IDRAC_HOST')
    if not host:
        host = input("Enter iDRAC host/IP: ").strip()
    
    if not host:
        print("No host provided. Exiting.")
        return
    
    # Get SNMP configuration
    community = env_vars.get('IDRAC_COMMUNITY', 'public')
    port = int(env_vars.get('IDRAC_PORT', 161))
    snmp_version = env_vars.get('SNMP_VERSION', 'v2c')
    username = env_vars.get('SNMP_USERNAME')
    auth_password = env_vars.get('SNMP_AUTH_PASSWORD')
    priv_password = env_vars.get('SNMP_PRIV_PASSWORD')
    
    print(f"\nTesting SNMP connection:")
    print(f"  Host: {host}")
    print(f"  SNMP Version: {snmp_version}")
    if snmp_version == "v3":
        print(f"  Username: {username}")
        print(f"  Auth Password: {'*' * len(auth_password) if auth_password else 'None'}")
        print(f"  Priv Password: {'*' * len(priv_password) if priv_password else 'None'}")
    else:
        print(f"  Community: {community}")
    print(f"  Port: {port}")
    
    # Create client and run tests
    client = SimpleSnmpClient(
        host=host, 
        community=community, 
        port=port,
        snmp_version=snmp_version,
        username=username,
        auth_password=auth_password,
        priv_password=priv_password
    )
    
    tests_passed = 0
    total_tests = 3
    
    # Test connectivity
    if await test_basic_connectivity(client):
        tests_passed += 1
    
    # Test Dell-specific OIDs
    if await test_dell_specific_oids(client):
        tests_passed += 1
    
    # Test sensor OIDs
    if await test_sensor_oids(client):
        tests_passed += 1
    
    # Run discovery walks (informational)
    await test_snmp_walks(client)
    
    # Summary
    print(f"\n{'='*30}")
    print(f"Test Results: {tests_passed}/{total_tests} test categories passed")
    
    if tests_passed == total_tests:
        print("✓ All tests passed! SNMP is working correctly.")
    elif tests_passed > 0:
        print(f"⚠ Partial success. Some tests failed.")
    else:
        print("✗ All tests failed. SNMP may not be properly configured.")
    
    print("\nNext steps:")
    if tests_passed > 0:
        print("1. SNMP connectivity is working")
        print("2. Check Home Assistant logs for integration-specific issues")
        print("3. Verify sensor discovery configuration")
    else:
        print("1. Verify iDRAC SNMP is enabled")
        print("2. Check SNMP community string")
        print("3. Ensure firewall allows UDP 161")
        print("4. Test network connectivity")


if __name__ == "__main__":
    asyncio.run(main())