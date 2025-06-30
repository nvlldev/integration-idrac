#!/usr/bin/env python3
"""
Manual sensor comparison analysis based on Home Assistant logs.
"""

# Your current sensors from the Home Assistant log:
current_sensors = {
    "snmp": {
        "temperatures": 6,  # All temperature sensors using SNMP
        "fans": 7,          # All fan sensors using SNMP  
        "power_consumption": 2,  # Power consumption using SNMP
        "memory": 1,        # Memory info using SNMP
        "diagnostics": 1    # SNMP response time sensor
    },
    "redfish": {
        "voltages": 4,      # All 4 voltage sensors using Redfish
        "system_info": 8,   # All system info using Redfish
        "diagnostics": 1    # Redfish response time sensor
    }
}

# SNMP voltage sensors we discovered
snmp_voltage_sensors = [
    "CPU1 VCORE PG",
    "CPU2 VCORE PG", 
    "System Board 3.3V PG",
    "System Board 5V AUX PG",
    "CPU2 M23 VPP PG",
    "CPU1 M23 VPP PG",
    "System Board 1.05V PG",
    "CPU1 M23 VDDQ PG", 
    "CPU1 M23 VTT PG",
    "System Board 5V SWITCH PG"
]

def analyze_optimization():
    print("SENSOR OPTIMIZATION ANALYSIS")
    print("="*50)
    print()
    
    print("CURRENT SENSOR DISTRIBUTION:")
    total_snmp = sum(current_sensors["snmp"].values())
    total_redfish = sum(current_sensors["redfish"].values())
    total = total_snmp + total_redfish
    
    print(f"  Total sensors: {total}")
    print(f"  SNMP sensors: {total_snmp} ({total_snmp/total*100:.1f}%)")
    print(f"  Redfish sensors: {total_redfish} ({total_redfish/total*100:.1f}%)")
    print()
    
    print("VOLTAGE SENSOR ANALYSIS:")
    print(f"  Current: {current_sensors['redfish']['voltages']} voltage sensors via Redfish")
    print(f"  Available via SNMP: {len(snmp_voltage_sensors)} power-good sensors")
    print()
    
    print("VOLTAGE SENSOR TYPES:")
    print("  Current Redfish sensors (likely actual voltage readings):")
    print("    - PSU Input Voltage sensors from PowerSupplies.LineInputVoltage")
    print("    - Probably actual voltage values (e.g., 120V, 230V)")
    print()
    
    print("  Available SNMP sensors (power-good status):")
    for i, sensor in enumerate(snmp_voltage_sensors, 1):
        print(f"    {i:2d}. {sensor}")
    print()
    
    print("OPTIMIZATION RECOMMENDATIONS:")
    print()
    
    print("1. VOLTAGE SENSORS - LIMITED OPTIMIZATION POTENTIAL:")
    print("   - Your current 4 Redfish voltage sensors are likely PSU input voltages")
    print("   - SNMP provides 10 power-good sensors (status only, no readings)")
    print("   - These serve different purposes:")
    print("     * Redfish: Actual voltage measurements (120V, 230V)")
    print("     * SNMP: Power rail status monitoring (OK/Failed)")
    print("   - RECOMMENDATION: Keep current Redfish voltage sensors")
    print("   - OPTIONAL: Add SNMP power-good sensors as binary sensors for diagnostics")
    print()
    
    print("2. SYSTEM INFO SENSORS - POTENTIAL OPTIMIZATION:")
    print(f"   - Current: {current_sensors['redfish']['system_info']} sensors via Redfish")
    print("   - SNMP likely has processor, memory, and system information")
    print("   - RECOMMENDATION: Test SNMP for processor/memory info")
    print("   - Potential optimization: 2-4 sensors could switch from Redfish to SNMP")
    print()
    
    print("3. OVERALL ASSESSMENT:")
    print("   - Your integration is already well-optimized!")
    print(f"   - {total_snmp}/{total} sensors ({total_snmp/total*100:.1f}%) already use SNMP")
    print("   - Temperature, fans, and power consumption optimally use SNMP")
    print("   - Voltage sensors appropriately use Redfish for actual readings")
    print()
    
    print("4. NEXT STEPS:")
    print("   a) Test processor/memory sensors via SNMP:")
    print("      python3 processor_snmp_test.py 192.168.50.131")
    print("   b) Consider adding SNMP power-good sensors as binary sensors")
    print("   c) Your current setup is already quite optimal!")
    print()
    
    print("PERFORMANCE IMPACT ANALYSIS:")
    snmp_percentage = total_snmp / total * 100
    if snmp_percentage >= 50:
        print(f"✅ EXCELLENT: {snmp_percentage:.1f}% of sensors use fast SNMP")
    elif snmp_percentage >= 30:
        print(f"✅ GOOD: {snmp_percentage:.1f}% of sensors use SNMP")
    else:
        print(f"⚠️  OPTIMIZATION NEEDED: Only {snmp_percentage:.1f}% use SNMP")
    
    print(f"   - SNMP sensors update every 15 seconds")
    print(f"   - Redfish sensors update every 45 seconds")
    print(f"   - Network load is well-balanced")

if __name__ == "__main__":
    analyze_optimization()