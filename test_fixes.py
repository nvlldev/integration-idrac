#!/usr/bin/env python3
"""Test the implementation fixes for the iDRAC integration."""

import asyncio
import sys
import os
import logging

# Add the current directory to Python path for imports
sys.path.insert(0, '/Users/scottpetersen/Development/TSHQ/Home Assistant/integration-idrac')

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

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

class MockConfigEntry:
    """Mock Home Assistant config entry."""
    
    def __init__(self, entry_id: str, **kwargs):
        self.entry_id = entry_id
        self.data = kwargs

async def test_snmp_client():
    """Test the SNMP client implementation with fixes."""
    print("Testing SNMP Client Implementation Fixes")
    print("=" * 50)
    
    try:
        # Import our modified SNMP client
        from custom_components.idrac.snmp.snmp_client import SNMPClient
        from custom_components.idrac.const import (
            CONF_COMMUNITY, CONF_SNMP_VERSION, CONF_SNMP_PORT,
            CONF_DISCOVERED_CPUS, CONF_DISCOVERED_FANS, CONF_DISCOVERED_PSUS,
            CONF_DISCOVERED_VOLTAGE_PROBES, CONF_DISCOVERED_MEMORY,
        )
        from homeassistant.const import CONF_HOST
        
        # Load configuration from .env
        env_vars = load_env_file()
        
        # Create mock config entry with discovered sensors (simulating what discovery found)
        config_entry = MockConfigEntry(
            entry_id="test_entry",
            **{
                CONF_HOST: env_vars.get('IDRAC_HOST', '192.168.50.130'),
                CONF_COMMUNITY: env_vars.get('IDRAC_COMMUNITY', 'public'),
                CONF_SNMP_VERSION: env_vars.get('SNMP_VERSION', 'v2c'),
                CONF_SNMP_PORT: int(env_vars.get('IDRAC_PORT', 161)),
                # Use sensor indices found from our earlier test
                CONF_DISCOVERED_CPUS: [1, 2, 3],  # Test with multiple indices
                CONF_DISCOVERED_FANS: [1, 2, 3, 4],
                CONF_DISCOVERED_PSUS: [1, 2],
                CONF_DISCOVERED_VOLTAGE_PROBES: [1, 2],
                CONF_DISCOVERED_MEMORY: [1, 2, 3, 4],
            }
        )
        
        print(f"Testing with configuration:")
        print(f"  Host: {config_entry.data[CONF_HOST]}")
        print(f"  SNMP Version: {config_entry.data[CONF_SNMP_VERSION]}")
        print(f"  Community: {config_entry.data[CONF_COMMUNITY]}")
        print(f"  Discovered CPUs: {config_entry.data[CONF_DISCOVERED_CPUS]}")
        print(f"  Discovered Fans: {config_entry.data[CONF_DISCOVERED_FANS]}")
        
        # Create SNMP client
        client = SNMPClient(config_entry)
        
        # Test device info
        print("\n--- Testing Device Info ---")
        device_info = await client.get_device_info()
        if device_info:
            print("✓ Device info retrieved:")
            for key, value in device_info.items():
                print(f"  {key}: {value}")
        else:
            print("✗ Failed to get device info")
        
        # Test sensor data collection
        print("\n--- Testing Sensor Data Collection ---")
        sensor_data = await client.get_sensor_data()
        
        if sensor_data:
            print("✓ Sensor data collected successfully!")
            print(f"Data categories found: {list(sensor_data.keys())}")
            
            # Check each category
            for category, data in sensor_data.items():
                if data:
                    print(f"  {category}: {len(data)} sensors found")
                    # Show first sensor as example
                    if isinstance(data, dict) and data:
                        first_sensor = next(iter(data.items()))
                        print(f"    Example: {first_sensor[0]} -> {first_sensor[1]}")
                else:
                    print(f"  {category}: No data")
            
            return True
        else:
            print("✗ No sensor data collected")
            return False
            
    except Exception as e:
        print(f"✗ Error testing SNMP client: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_sensor_availability():
    """Test the sensor availability logic."""
    print("\n--- Testing Sensor Availability Logic ---")
    
    try:
        from custom_components.idrac.sensor import IdracSensor
        from custom_components.idrac.coordinator import IdracDataUpdateCoordinator
        
        # Mock coordinator with partial data (simulating real-world scenario)
        class MockCoordinator:
            def __init__(self):
                self.data = {
                    "temperatures": {
                        "cpu_temp_1": {"name": "CPU 1 Temp", "temperature": 45.0, "status": "ok"}
                    },
                    "fans": {
                        "fan_1": {"name": "Fan 1", "speed_rpm": 2880, "status": "ok"}
                    }
                    # Note: no power_supplies, memory, etc. - simulating partial failure
                }
                self.last_update_success = True
                self.device_info = {"model": "PowerEdge R820", "name": "Test Server"}
        
        # Test temperature sensor availability (should be available)
        class TestTempSensor(IdracSensor):
            def __init__(self):
                self.coordinator = MockCoordinator()
                self.temp_id = "cpu_temp_1"
                self.sensor_type = "temperature_cpu_temp_1"
        
        temp_sensor = TestTempSensor()
        temp_available = temp_sensor.available
        print(f"✓ Temperature sensor availability: {temp_available} (should be True)")
        
        # Test missing sensor availability (should be unavailable)
        class TestMissingSensor(IdracSensor):
            def __init__(self):
                self.coordinator = MockCoordinator()
                self.psu_id = "psu_1"  # This doesn't exist in mock data
                self.sensor_type = "psu_psu_1_status"
        
        missing_sensor = TestMissingSensor()
        missing_available = missing_sensor.available
        print(f"✓ Missing PSU sensor availability: {missing_available} (should be False)")
        
        # Test fan sensor availability (should be available)
        class TestFanSensor(IdracSensor):
            def __init__(self):
                self.coordinator = MockCoordinator()
                self.fan_id = "fan_1"
                self.sensor_type = "fan_fan_1"
        
        fan_sensor = TestFanSensor()
        fan_available = fan_sensor.available
        print(f"✓ Fan sensor availability: {fan_available} (should be True)")
        
        return temp_available and not missing_available and fan_available
        
    except Exception as e:
        print(f"✗ Error testing sensor availability: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests."""
    print("iDRAC Integration Implementation Fix Tests")
    print("=" * 60)
    
    # Test SNMP client
    snmp_test_passed = await test_snmp_client()
    
    # Test sensor availability logic
    availability_test_passed = await test_sensor_availability()
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Results Summary:")
    print(f"  SNMP Client Test: {'✓ PASSED' if snmp_test_passed else '✗ FAILED'}")
    print(f"  Availability Test: {'✓ PASSED' if availability_test_passed else '✗ FAILED'}")
    
    if snmp_test_passed and availability_test_passed:
        print("\n🎉 All tests passed! The implementation fixes should resolve the unavailable sensors issue.")
        print("\nNext steps:")
        print("1. Restart Home Assistant to load the changes")
        print("2. Check Home Assistant logs for debug messages")
        print("3. Verify sensors now show as available")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    asyncio.run(main())