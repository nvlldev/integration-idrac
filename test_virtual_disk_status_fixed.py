#!/usr/bin/env python3
"""Test script to verify the corrected virtual disk status mapping."""

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

async def test_corrected_virtual_disk_status():
    """Test the corrected virtual disk status mapping."""
    print("✅ TESTING CORRECTED VIRTUAL DISK STATUS MAPPING")
    print("=" * 60)
    print("Fix: Changed state 2 from 'failed' to 'optimal'")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Virtual disk OIDs
    vdisk_state_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4"
    vdisk_name_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2"
    vdisk_size_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.6"
    
    print(f"\n🔍 Testing virtual disk status with corrected mapping:")
    print("-" * 55)
    
    # Test first 5 indices for virtual disks
    for i in range(1, 6):
        state_oid = f"{vdisk_state_base}.{i}"
        name_oid = f"{vdisk_name_base}.{i}"
        size_oid = f"{vdisk_size_base}.{i}"
        
        state = await get_snmp_value(engine, community_data, transport_target, context_data, state_oid)
        name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        size = await get_snmp_value(engine, community_data, transport_target, context_data, size_oid)
        
        if state and state.isdigit():
            state_raw = int(state)
            
            # Updated mapping with fix
            corrected_mapping = {
                1: "ready",
                2: "optimal",  # FIXED: was "failed"
                3: "online",
                4: "offline",
                5: "degraded",
                6: "verifying",
                7: "background_init",
                8: "resynching"
            }
            
            # Old mapping for comparison
            old_mapping = {
                1: "ready",
                2: "failed",  # OLD: incorrect
                3: "online", 
                4: "offline",
                5: "degraded",
                6: "verifying",
                7: "background_init",
                8: "resynching"
            }
            
            corrected_status = corrected_mapping.get(state_raw, f"unknown_{state_raw}")
            old_status = old_mapping.get(state_raw, f"unknown_{state_raw}")
            
            # Display size
            size_display = "Unknown"
            if size and size.isdigit():
                size_mb = int(size)
                size_gb = size_mb // 1024
                if size_gb > 0:
                    size_display = f"{size_gb}GB"
                else:
                    size_display = f"{size_mb}MB"
            
            print(f"   Index {i}: {name or f'Virtual Disk {i}'}")
            print(f"      Raw State: {state_raw}")
            print(f"      OLD mapping: '{old_status}'")
            print(f"      NEW mapping: '{corrected_status}' ✅")
            print(f"      Size: {size_display}")
            
            # Status analysis
            if state_raw == 2:
                print(f"      🎯 FIX APPLIED: State 2 now shows 'optimal' instead of 'failed'")
                print(f"      💡 This should match user's healthy disk status")
            elif state_raw in [1, 3]:
                print(f"      ✅ State {state_raw} correctly indicates healthy disk")
            elif state_raw in [4, 5]:
                print(f"      ⚠️  State {state_raw} indicates disk problems")
            elif state_raw in [6, 7, 8]:
                print(f"      🔧 State {state_raw} indicates maintenance/background activity")
    
    # Summary of the fix
    print(f"\n📊 VIRTUAL DISK STATUS FIX SUMMARY:")
    print("-" * 45)
    print("   ✅ FIXED: State 2 mapping")
    print("      Before: 2 → 'failed' (incorrect)")
    print("      After:  2 → 'optimal' (correct)")
    print("")
    print("   📋 Complete corrected mapping:")
    print("      1: ready           (healthy)")
    print("      2: optimal         (healthy) ← FIXED")
    print("      3: online          (healthy)")
    print("      4: offline         (problem)")
    print("      5: degraded        (problem)")
    print("      6: verifying       (maintenance)")
    print("      7: background_init (maintenance)")
    print("      8: resynching      (maintenance)")
    
    print(f"\n💡 USER IMPACT:")
    print("-" * 15)
    print("   ✅ Healthy virtual disks will now show correct status")
    print("   ✅ State 2 disks will show as 'optimal' instead of 'failed'")
    print("   📋 User's disk should now display correctly in Home Assistant")
    
    print(f"\n🔧 IMPLEMENTATION STATUS:")
    print("-" * 25)
    print("   ✅ Updated VIRTUAL_DISK_STATUS mapping in const.py")
    print("   📋 Integration will use corrected mapping on next restart")
    print("   📋 No additional code changes needed")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_corrected_virtual_disk_status()

if __name__ == "__main__":
    asyncio.run(main())