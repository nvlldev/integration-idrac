#!/usr/bin/env python3
"""Test script to discover all CPU temperature sensors."""

import asyncio
import os
from dotenv import load_dotenv
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

# Load environment variables
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

async def get_snmp_value(engine, community_data, transport_target, context_data, oid):
    """Get a single SNMP value."""
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid)),
        )
        
        if not error_indication and not error_status and var_binds:
            value = str(var_binds[0][1]).strip()
            if value and "No Such" not in value:
                return value
        return None
    except Exception:
        return None

async def discover_cpu_temperatures():
    """Discover all available CPU temperature sensors."""
    print("🌡️ DISCOVERING CPU TEMPERATURE SENSORS")
    print("=" * 60)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test extended range of temperature sensor indices
    print("\n🔍 Testing temperature sensor indices (1-10):")
    print("-" * 50)
    
    temp_base_oid = "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1"
    temp_name_base_oid = "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1"
    
    found_sensors = []
    
    for i in range(1, 11):  # Test indices 1-10
        temp_oid = f"{temp_base_oid}.{i}"
        name_oid = f"{temp_name_base_oid}.{i}"
        
        temp_value = await get_snmp_value(engine, community_data, transport_target, context_data, temp_oid)
        temp_name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        
        if temp_value is not None:
            try:
                temp_celsius = float(temp_value) / 10 if temp_value.isdigit() else temp_value
                sensor_info = {
                    'index': i,
                    'name': temp_name or f"Temperature Sensor {i}",
                    'value': temp_celsius,
                    'raw_value': temp_value
                }
                found_sensors.append(sensor_info)
                
                # Determine sensor type
                sensor_type = "Unknown"
                if temp_name:
                    name_lower = temp_name.lower()
                    if "cpu" in name_lower:
                        sensor_type = "CPU"
                    elif "inlet" in name_lower:
                        sensor_type = "Inlet"
                    elif "exhaust" in name_lower or "outlet" in name_lower:
                        sensor_type = "Exhaust"
                    elif "system" in name_lower:
                        sensor_type = "System"
                
                print(f"   Index {i}: {temp_name} = {temp_celsius}°C [{sensor_type}]")
            except (ValueError, TypeError):
                print(f"   Index {i}: {temp_name} = {temp_value} (non-numeric)")
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print("-" * 20)
    print(f"   Found {len(found_sensors)} temperature sensors")
    
    cpu_sensors = [s for s in found_sensors if s['name'] and 'cpu' in s['name'].lower()]
    system_sensors = [s for s in found_sensors if s['name'] and any(x in s['name'].lower() for x in ['inlet', 'exhaust', 'system', 'board'])]
    
    print(f"   CPU sensors: {len(cpu_sensors)}")
    for cpu in cpu_sensors:
        print(f"     - Index {cpu['index']}: {cpu['name']} = {cpu['value']}°C")
    
    print(f"   System sensors: {len(system_sensors)}")
    for sys in system_sensors:
        print(f"     - Index {sys['index']}: {sys['name']} = {sys['value']}°C")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 25)
    if len(cpu_sensors) > 1:
        print("   ✅ Multiple CPU temperature sensors found!")
        print("   📋 Suggest updating discovery to include all CPU sensors:")
        cpu_indices = [str(cpu['index']) for cpu in cpu_sensors]
        print(f"      CPU indices: {', '.join(cpu_indices)}")
    elif len(cpu_sensors) == 1:
        print("   ⚠️  Only one CPU temperature sensor found")
        print("   🔍 This may be expected for single-CPU systems")
    else:
        print("   ❌ No CPU temperature sensors found")
    
    return found_sensors

async def main():
    """Main discovery function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await discover_cpu_temperatures()

if __name__ == "__main__":
    asyncio.run(main())