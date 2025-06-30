#!/usr/bin/env python3
"""
Debug Power Consumption Source
Check which coordinator (SNMP vs Redfish) is providing power data
"""

def check_power_source():
    """Analyze power consumption sensor source."""
    
    print("🔌 POWER CONSUMPTION SENSOR DEBUG")
    print("=" * 50)
    print()
    
    print("📋 CONFIGURATION:")
    print("  - sensor.py line 116: ('power_consumption', IdracPowerConsumptionSensor, 'snmp')")
    print("  - This sets SNMP as the preferred source")
    print()
    
    print("🔍 HOW IT WORKS:")
    print("  1. get_coordinator_for_category() checks SNMP first (preferred='snmp')")
    print("  2. If SNMP has 'power_consumption' data, it uses SNMP")
    print("  3. If not, it falls back to Redfish")
    print()
    
    print("📊 SNMP POWER CONSUMPTION:")
    print("  - Current Power OID: 1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3")
    print("  - Peak Power OID: 1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3")
    print("  - Discovery checks the .3 OID directly (fixed, not indexed)")
    print("  - Data format: {'consumed_watts': X, 'max_consumed_watts': Y}")
    print()
    
    print("📊 REDFISH POWER CONSUMPTION:")
    print("  - Path: /redfish/v1/Chassis/.../Power")
    print("  - PowerControl[0].PowerConsumedWatts")
    print("  - Also provides average, min, max from PowerMetrics")
    print()
    
    print("🐛 POTENTIAL ISSUES:")
    print("  1. SNMP discovery might fail if OID returns non-numeric value")
    print("  2. discovered_power_consumption might be empty []")
    print("  3. SNMP coordinator might not have the data")
    print()
    
    print("✅ TO VERIFY SNMP IS WORKING:")
    print("  1. Run test_snmp_power.py to check if OID returns data")
    print("  2. Check logs for 'Power consumption sensor discovery'")
    print("  3. Look for 'Found power consumption sensor at OID'")
    print("  4. Check sensor source in Home Assistant Developer Tools")
    print()
    
    print("📝 DEBUG STEPS:")
    print("  1. Enable debug logging:")
    print("     logger:")
    print("       logs:")
    print("         custom_components.idrac: debug")
    print("  2. Restart integration")
    print("  3. Check logs for:")
    print("     - 'Starting power consumption sensor discovery'")
    print("     - 'Creating 1 power_consumption sensors using...'")
    print("     - Which coordinator name appears")
    print()
    
    print("🔧 IF USING REDFISH INSTEAD OF SNMP:")
    print("  - SNMP discovery failed to find the power OID")
    print("  - Check if iDRAC firmware supports power via SNMP")
    print("  - Some older iDRACs might not expose power via SNMP")

if __name__ == "__main__":
    check_power_source()
    
    print("\n" + "=" * 50)
    print("💡 TIP: The power sensor will show which coordinator it's using")
    print("   in the Home Assistant entity attributes or debug logs.")