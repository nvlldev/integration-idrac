#!/usr/bin/env python3
"""Test script to discover the full range of memory modules for enterprise configurations."""

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

async def test_memory_discovery_range():
    """Test memory discovery for enterprise configurations supporting up to 48 DIMMs, 4 CPUs."""
    print("🧠 TESTING MEMORY DISCOVERY RANGE FOR ENTERPRISE CONFIGS")
    print("=" * 70)
    print("Target: Support up to 48 DIMMs across 4 CPUs (12 DIMMs per CPU)")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Memory OID bases from const.py
    memory_health_base = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1"  # Memory health status
    memory_size_base = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1"   # Memory device size
    memory_location_base = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1" # Memory device location
    memory_speed_base = "1.3.6.1.4.1.674.10892.5.4.1100.50.1.27.1"   # Memory device speed
    
    print(f"\n🔍 Testing memory module indices (1-50) for enterprise support:")
    print("-" * 70)
    
    found_modules = []
    
    # Test extended range for enterprise configurations  
    for i in range(1, 51):  # Test 1-50 to cover enterprise configurations
        health_oid = f"{memory_health_base}.{i}"
        size_oid = f"{memory_size_base}.{i}"
        location_oid = f"{memory_location_base}.{i}"
        speed_oid = f"{memory_speed_base}.{i}"
        
        health = await get_snmp_value(engine, community_data, transport_target, context_data, health_oid)
        size = await get_snmp_value(engine, community_data, transport_target, context_data, size_oid)
        location = await get_snmp_value(engine, community_data, transport_target, context_data, location_oid)
        speed = await get_snmp_value(engine, community_data, transport_target, context_data, speed_oid)
        
        # Check if module exists (has health status or size)
        if health or (size and size.isdigit() and int(size) > 0):
            module_info = {
                'index': i,
                'health': health,
                'size_kb': size,
                'location': location,
                'speed_mhz': speed
            }
            
            found_modules.append(module_info)
            
            # Calculate size in MB/GB for display
            size_display = "Unknown"
            if size and size.isdigit():
                size_kb = int(size)
                size_mb = size_kb // 1024
                size_gb = size_mb // 1024
                if size_gb > 0:
                    size_display = f"{size_gb}GB"
                else:
                    size_display = f"{size_mb}MB"
            
            # Map health status
            health_map = {
                "1": "other",
                "2": "ready", 
                "3": "ok",
                "4": "non_critical",
                "5": "critical",
                "6": "non_recoverable"
            }
            health_display = health_map.get(health, health) if health else "unknown"
            
            print(f"   Index {i:2d}: {location} - {size_display} @ {speed}MHz [Health: {health_display}]")
    
    # Analyze findings for enterprise support
    print(f"\n📊 MEMORY DISCOVERY ANALYSIS:")
    print("-" * 40)
    print(f"   Total memory modules found: {len(found_modules)}")
    
    # Group by CPU if possible
    cpu_groups = {}
    for module in found_modules:
        location = module.get('location', '')
        if location:
            # Extract CPU info from location string (e.g., "DIMM.Socket.A1", "CPU1_DIMM_A1")
            cpu_num = "Unknown"
            if 'DIMM.Socket.A' in location:
                cpu_num = "CPU1"
            elif 'DIMM.Socket.B' in location:
                cpu_num = "CPU2" 
            elif 'DIMM.Socket.C' in location:
                cpu_num = "CPU3"
            elif 'DIMM.Socket.D' in location:
                cpu_num = "CPU4"
            elif 'CPU' in location:
                # Try to extract CPU number from location
                import re
                match = re.search(r'CPU(\d+)', location)
                if match:
                    cpu_num = f"CPU{match.group(1)}"
            
            if cpu_num not in cpu_groups:
                cpu_groups[cpu_num] = []
            cpu_groups[cpu_num].append(module)
    
    print(f"   Memory modules per CPU:")
    for cpu, modules in sorted(cpu_groups.items()):
        print(f"     {cpu}: {len(modules)} modules")
        if len(modules) <= 4:  # Show first few module locations
            for mod in modules[:4]:
                print(f"       - Index {mod['index']}: {mod['location']}")
        if len(modules) > 4:
            print(f"       - ... and {len(modules)-4} more")
    
    # Enterprise configuration recommendations
    print(f"\n💡 ENTERPRISE CONFIGURATION SUPPORT:")
    print("-" * 45)
    
    max_index = max(module['index'] for module in found_modules) if found_modules else 0
    
    print(f"   Current max memory index found: {max_index}")
    print(f"   Current discovery range (config_flow): 1-20")
    
    if max_index > 20:
        print(f"   ⚠️  ISSUE: Found memory beyond current discovery range!")
        print(f"   📋 RECOMMENDATION: Increase discovery range to at least {max_index + 10}")
    elif len(found_modules) >= 16:
        print(f"   ✅ Current system has {len(found_modules)} modules - adequate for most enterprise configs")
        print(f"   📋 RECOMMENDATION: Consider increasing discovery range to 50 for maximum enterprise support")
    else:
        print(f"   ✅ Current configuration fits within discovery range")
        print(f"   📋 RECOMMENDATION: Still increase range to 50 for enterprise servers with 48 DIMMs")
    
    print(f"\n🔧 PROPOSED FIXES:")
    print("-" * 20)
    print("   1. Update config_flow._discover_sensors range from 1-20 to 1-50")
    print("   2. This will support enterprise configurations with up to 48 DIMMs across 4 CPUs")
    print("   3. Test with enterprise servers to ensure proper discovery")
    
    return found_modules, max_index

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_memory_discovery_range()

if __name__ == "__main__":
    asyncio.run(main())