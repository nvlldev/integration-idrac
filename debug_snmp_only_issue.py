#!/usr/bin/env python3
"""
Debug SNMP-Only Mode Issue
Check why no devices/entities are created in SNMP-only mode
"""

import json
from datetime import datetime

def analyze_snmp_only_issue():
    """Analyze potential issues with SNMP-only mode."""
    
    print("🔍 DEBUGGING SNMP-ONLY MODE ISSUE")
    print("=" * 50)
    print()
    
    print("📋 ISSUE: No devices or entities created in SNMP-only mode")
    print()
    
    print("🔗 POSSIBLE CAUSES:")
    print()
    
    print("1. ❓ DISCOVERED SENSORS NOT SAVED:")
    print("   - Config flow discovers sensors during validation")
    print("   - Discovered sensor lists stored in data[] dict") 
    print("   - These should be saved to entry.data via async_create_entry")
    print("   - SNMPClient reads them from entry.data")
    print()
    
    print("2. ❓ SNMP COORDINATOR NOT GETTING DATA:")
    print("   - SNMPDataUpdateCoordinator creates SNMPCoordinator")
    print("   - SNMPCoordinator creates SNMPClient(entry)")
    print("   - SNMPClient needs discovered sensors from entry.data")
    print("   - If no discovered sensors, client returns empty data")
    print()
    
    print("3. ❓ SENSOR SETUP SKIPPING CATEGORIES:")
    print("   - sensor.py checks: if coordinator.data and category in coordinator.data")
    print("   - If SNMP returns empty dict, no sensors created")
    print("   - Need to verify SNMP client returns proper structure")
    print()
    
    print("🔧 DEBUGGING STEPS:")
    print()
    
    steps = [
        "1. Check Home Assistant logs for SNMP discovery during config",
        "2. Look for 'Discovered X fans, Y temperatures...' log messages",
        "3. Check if entry.data contains discovered_fans, discovered_cpus, etc.",
        "4. Verify SNMP coordinator initialization logs",
        "5. Check for 'No sensors discovered during setup' warning",
        "6. Look for 'Runtime discovery' attempts",
        "7. Check if get_sensor_data returns proper category structure"
    ]
    
    for step in steps:
        print(f"   {step}")
    
    print()
    print("📝 EXPECTED LOG SEQUENCE:")
    print()
    
    expected_logs = [
        "Config flow: 'Discovered 6 fans, 4 CPU temperature sensors...'",
        "Init: 'Connection mode: snmp_only - Created 1 coordinators'",
        "SNMPClient: 'Loading discovered sensors from config entry'",
        "SNMPClient: 'SNMP data collection for 40+ sensors'",
        "Sensor: 'Creating 6 fans sensors using SNMPDataUpdateCoordinator'",
        "Sensor: 'Creating 4 temperatures sensors using SNMPDataUpdateCoordinator'"
    ]
    
    for log in expected_logs:
        print(f"   ✓ {log}")
    
    print()
    print("🔍 LIKELY ISSUE:")
    print("   The discovered sensors from config flow validation are not")
    print("   being persisted to entry.data, causing SNMPClient to have")
    print("   no sensors to query, resulting in empty coordinator.data")
    print()
    
    print("💡 SOLUTION:")
    print("   Ensure validate_snmp_input() stores discovered sensors in data dict")
    print("   before returning, so they're saved via async_create_entry()")
    
    # Generate test configuration
    test_config = {
        "entry_data_expected": {
            "host": "192.168.50.131",
            "connection_type": "snmp_only",
            "snmp_version": "v2c", 
            "snmp_community": "public",
            "snmp_port": 161,
            "discovered_fans": [1, 2, 3, 4, 5, 6],
            "discovered_cpus": [1, 2],
            "discovered_temperatures": [1, 2, 3, 4],
            "discovered_psus": [1, 2],
            "discovered_memory": [1, 2, 3, 4, 5, 6, 7, 8],
            # ... other discovered sensors
        },
        "snmp_client_check": {
            "self.discovered_fans": "Should be [1, 2, 3, 4, 5, 6]",
            "self.discovered_cpus": "Should be [1, 2]",
            "get_sensor_data()": "Should return dict with categories"
        }
    }
    
    return test_config

if __name__ == "__main__":
    config = analyze_snmp_only_issue()
    
    print()
    print("📋 CHECK ENTRY.DATA CONTENTS:")
    print("=" * 50)
    print(json.dumps(config["entry_data_expected"], indent=2))
    
    print()
    print("🎯 NEXT STEP:")
    print("   Check if validate_snmp_input() in config_flow.py")
    print("   properly stores discovered sensors in the data dict")
    print("   that gets passed to async_create_entry()")