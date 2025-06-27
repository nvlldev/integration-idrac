#!/usr/bin/env python3
"""Test script to investigate virtual disk status mapping."""

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

async def test_virtual_disk_status():
    """Test virtual disk status mapping to identify the correct values."""
    print("💾 TESTING VIRTUAL DISK STATUS MAPPING")
    print("=" * 50)
    print("Issue: Virtual disk showing as failed when it's healthy")
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Virtual disk OIDs from const.py
    vdisk_state_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4"     # Virtual disk state
    vdisk_name_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2"      # Virtual disk name
    vdisk_size_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.6"      # Virtual disk size
    vdisk_layout_base = "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.13"   # Virtual disk layout
    
    print(f"\n🔍 Discovering virtual disks:")
    print("-" * 35)
    
    found_vdisks = []
    
    # Test first 10 indices for virtual disks
    for i in range(1, 11):
        state_oid = f"{vdisk_state_base}.{i}"
        name_oid = f"{vdisk_name_base}.{i}"
        size_oid = f"{vdisk_size_base}.{i}"
        layout_oid = f"{vdisk_layout_base}.{i}"
        
        state = await get_snmp_value(engine, community_data, transport_target, context_data, state_oid)
        name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        size = await get_snmp_value(engine, community_data, transport_target, context_data, size_oid)
        layout = await get_snmp_value(engine, community_data, transport_target, context_data, layout_oid)
        
        # Check if virtual disk exists
        if state and state.isdigit():
            vdisk_info = {
                'index': i,
                'state_raw': int(state),
                'name': name or f"Virtual Disk {i}",
                'size_mb': size,
                'layout': layout
            }
            
            found_vdisks.append(vdisk_info)
            
            # Current mapping from const.py
            current_mapping = {
                1: "ready",
                2: "failed", 
                3: "online",
                4: "offline",
                5: "degraded",
                6: "verifying",
                7: "background_init",
                8: "resynching"
            }
            
            current_status = current_mapping.get(int(state), f"unknown_{state}")
            
            # Calculate size in GB for display
            size_display = "Unknown"
            if size and size.isdigit():
                size_mb = int(size)
                size_gb = size_mb // 1024
                if size_gb > 0:
                    size_display = f"{size_gb}GB"
                else:
                    size_display = f"{size_mb}MB"
            
            # Layout mapping
            layout_mapping = {
                "1": "RAID-0",
                "2": "RAID-1", 
                "3": "RAID-5",
                "4": "RAID-6",
                "5": "RAID-10",
                "6": "RAID-50",
                "7": "RAID-60"
            }
            layout_display = layout_mapping.get(layout, layout) if layout else "Unknown"
            
            print(f"   Index {i}: {name}")
            print(f"      Raw State: {state} → Current Mapping: '{current_status}'")
            print(f"      Size: {size_display}, Layout: {layout_display}")
    
    # Analysis of status mappings
    print(f"\n📊 VIRTUAL DISK STATUS ANALYSIS:")
    print("-" * 40)
    print(f"   Found {len(found_vdisks)} virtual disk(s)")
    
    if found_vdisks:
        for vdisk in found_vdisks:
            state_raw = vdisk['state_raw']
            print(f"\n   Virtual Disk {vdisk['index']}: {vdisk['name']}")
            print(f"      Raw state value: {state_raw}")
            
            # Current mapping
            current_mapping = {
                1: "ready",
                2: "failed", 
                3: "online", 
                4: "offline",
                5: "degraded",
                6: "verifying",
                7: "background_init",
                8: "resynching"
            }
            current_status = current_mapping.get(state_raw, f"unknown_{state_raw}")
            print(f"      Current mapping: '{current_status}'")
            
            # Research Dell iDRAC documentation for correct mapping
            print(f"      Expected healthy states: ready(1), online(3)")
            print(f"      Expected problem states: failed(2), offline(4), degraded(5)")
            
            if state_raw == 2:
                print(f"      ⚠️  ISSUE: State 2 mapped to 'failed' - user says disk is healthy!")
                print(f"      🔍 Need to verify if state 2 actually means something else")
            elif state_raw in [1, 3]:
                print(f"      ✅ State {state_raw} correctly mapped as healthy")
    
    # Recommendations for fixing the mapping
    print(f"\n💡 STATUS MAPPING INVESTIGATION:")
    print("-" * 35)
    
    print("   Current mapping (from const.py):")
    print("     1: ready     (✅ healthy)")
    print("     2: failed    (❌ may be incorrect)")
    print("     3: online    (✅ healthy)")
    print("     4: offline   (❌ problem)")
    print("     5: degraded  (⚠️  problem)")
    print("     6: verifying (⚠️  maintenance)")
    print("     7: background_init (⚠️  maintenance)")
    print("     8: resynching (⚠️  maintenance)")
    
    print(f"\n🔧 POTENTIAL FIXES:")
    print("-" * 20)
    if found_vdisks:
        for vdisk in found_vdisks:
            if vdisk['state_raw'] == 2:
                print("   📋 State 2 investigation needed:")
                print("      - Check Dell MIB documentation")
                print("      - State 2 might be 'optimal' or 'normal' instead of 'failed'")
                print("      - Consider updating mapping: 2: 'optimal' or 2: 'ready'")
            elif vdisk['state_raw'] in [1, 3]:
                print(f"   ✅ State {vdisk['state_raw']} mapping appears correct")
    
    print(f"\n📚 DELL MIB REFERENCE:")
    print("-" * 25)
    print("   Need to verify against official Dell documentation:")
    print("   - virtualDiskState values in Dell OpenManage MIB")
    print("   - Common Dell iDRAC virtual disk states")
    print("   - User reported disk is healthy but shows as 'failed'")
    
    return found_vdisks

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_virtual_disk_status()

if __name__ == "__main__":
    asyncio.run(main())