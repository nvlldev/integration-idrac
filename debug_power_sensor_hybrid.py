#!/usr/bin/env python3
"""
Debug power sensor issues in hybrid mode
Comprehensive check for why power sensors aren't appearing
"""

import asyncio
import json
import os
from pathlib import Path
from pysnmp.hlapi.asyncio import (
    getCmd,
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
)

async def check_config_entry(host: str):
    """Check Home Assistant config entries for the host."""
    print("📁 CHECKING CONFIG ENTRY")
    print("=" * 60)
    
    # Typical location of Home Assistant config
    config_paths = [
        Path.home() / ".homeassistant" / ".storage" / "core.config_entries",
        Path("/config/.storage/core.config_entries"),
        Path("config/.storage/core.config_entries"),
    ]
    
    config_found = False
    for config_path in config_paths:
        if config_path.exists():
            print(f"Found config at: {config_path}")
            config_found = True
            
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Look for iDRAC entries
                for entry in config_data.get("data", {}).get("entries", []):
                    if entry.get("domain") == "idrac" and host in str(entry):
                        print(f"\n✅ Found iDRAC entry for {host}")
                        print(f"   Mode: {entry.get('data', {}).get('mode', 'Unknown')}")
                        
                        # Check for discovered sensors
                        discovered_power = entry.get('data', {}).get('discovered_power_consumption', None)
                        print(f"   discovered_power_consumption: {discovered_power}")
                        
                        if discovered_power is None:
                            print("   ⚠️  No power consumption discovery data!")
                            print("   This means discovery didn't find power sensors during setup")
                        elif not discovered_power:
                            print("   ⚠️  Empty power consumption discovery list!")
                        else:
                            print(f"   ✅ Power consumption sensors discovered: {discovered_power}")
                        
                        # Show all discovered sensor types
                        print("\n   All discovered sensors:")
                        for key, value in entry.get('data', {}).items():
                            if key.startswith('discovered_'):
                                print(f"   - {key}: {value if isinstance(value, list) else '...'}")
                        
                        return discovered_power
            except Exception as e:
                print(f"Error reading config: {e}")
    
    if not config_found:
        print("❌ Could not find Home Assistant config file")
        print("   Please provide the path to your .storage/core.config_entries file")
    
    return None

async def test_power_discovery(host: str, community: str = "public"):
    """Test power sensor discovery logic."""
    print("\n🔍 TESTING POWER DISCOVERY")
    print("=" * 60)
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport = UdpTransportTarget((host, 161))
    context = ContextData()
    
    # Base OID for power consumption
    base_oid = "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1"
    
    print(f"Testing discovery at base OID: {base_oid}")
    
    # Test index 3 (the integration specifically checks this)
    test_oid = f"{base_oid}.3"
    print(f"\n1️⃣ Testing fixed index 3: {test_oid}")
    
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport,
            context,
            ObjectType(ObjectIdentity(test_oid))
        )
        
        if not error_indication and not error_status:
            for var_name, var_value in var_binds:
                if str(var_value) != "No Such Object currently exists at this OID":
                    try:
                        watts = int(var_value)
                        print(f"   ✅ Found power at index 3: {watts} W")
                        print(f"   Integration should discover this as: discovered_power_consumption: [1]")
                    except:
                        print(f"   ❌ Non-numeric value: {var_value}")
                else:
                    print(f"   ❌ No power sensor at index 3")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test other indices (1-10) for legacy support
    print(f"\n2️⃣ Testing legacy indices 1-10:")
    found_indices = []
    
    for index in range(1, 11):
        test_oid = f"{base_oid}.{index}"
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(test_oid))
            )
            
            if not error_indication and not error_status:
                for var_name, var_value in var_binds:
                    if str(var_value) != "No Such Object currently exists at this OID":
                        try:
                            watts = int(var_value)
                            print(f"   Index {index}: {watts} W ✅")
                            found_indices.append(index)
                        except:
                            # Check for power-related strings
                            val_str = str(var_value).strip()
                            if val_str and any(kw in val_str for kw in ["Power", "Current", "Consumption", "PS"]):
                                print(f"   Index {index}: {val_str} (power-related string) ✅")
                                found_indices.append(index)
        except:
            pass
    
    if found_indices:
        print(f"\n   ✅ Power discovery should find indices: {found_indices}")
    else:
        print(f"\n   ❌ No power sensors found during discovery")
    
    # Test the actual power consumption OIDs
    print(f"\n3️⃣ Testing actual power consumption OIDs:")
    power_oids = {
        "current": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
        "peak": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3",
    }
    
    power_available = False
    for name, oid in power_oids.items():
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(oid))
            )
            
            if not error_indication and not error_status:
                for var_name, var_value in var_binds:
                    if str(var_value) != "No Such Object currently exists at this OID":
                        print(f"   {name}: {var_value} W ✅")
                        power_available = True
        except:
            pass
    
    engine.close()
    
    return power_available, found_indices

async def main(host: str, community: str = "public"):
    """Main debug function."""
    print(f"🔧 DEBUGGING POWER SENSOR FOR {host}")
    print("=" * 60)
    
    # Check config entry
    discovered_in_config = await check_config_entry(host)
    
    # Test actual discovery
    power_available, found_indices = await test_power_discovery(host, community)
    
    # Analysis
    print("\n📊 ANALYSIS")
    print("=" * 60)
    
    if power_available:
        print("✅ Power monitoring is available via SNMP")
        
        if discovered_in_config is None:
            print("❌ Power sensors not in config entry - discovery didn't run or failed")
            print("\nSOLUTION: Remove and re-add the integration to trigger discovery")
        elif not discovered_in_config:
            print("❌ Power discovery returned empty list")
            print("\nPOSSIBLE ISSUE: Discovery logic may have a bug")
        else:
            print("✅ Power sensors are discovered in config")
            print("\nPOSSIBLE ISSUES:")
            print("1. SNMP coordinator not collecting power data")
            print("2. Sensor creation logic not creating power sensor")
            print("3. Check Home Assistant logs for errors")
    else:
        print("❌ Power monitoring not available via SNMP")
        print("   This iDRAC may not support power monitoring")
    
    print("\n💡 NEXT STEPS:")
    print("1. Check Home Assistant logs for:")
    print("   - 'Starting power consumption sensor discovery'")
    print("   - 'Found power consumption sensor at'")
    print("   - 'Creating 1 power_consumption sensors'")
    print("2. Enable debug logging:")
    print("   logger:")
    print("     default: info")
    print("     logs:")
    print("       custom_components.idrac: debug")
    print("3. Remove and re-add the integration if discovery data is missing")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 debug_power_sensor_hybrid.py <idrac_ip> [community]")
        sys.exit(1)
    
    HOST = sys.argv[1]
    COMMUNITY = sys.argv[2] if len(sys.argv) > 2 else "public"
    
    asyncio.run(main(HOST, COMMUNITY))