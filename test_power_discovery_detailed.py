#!/usr/bin/env python3
"""
Detailed test of power sensor discovery
Tests the exact logic used by the integration
"""

import asyncio
from pysnmp.hlapi.asyncio import (
    getCmd,
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
)

async def test_discovery_logic(host: str, community: str = "public"):
    """Test the exact discovery logic from snmp_discovery.py"""
    print(f"🔍 Testing Power Discovery Logic for {host}")
    print("=" * 60)
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, 161))
    context_data = ContextData()
    
    base_oid = "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1"
    discovered_sensors = []
    
    # First check index 3 (as per the integration code)
    print(f"\n1️⃣ Checking fixed index 3 (integration's primary check):")
    test_oid = f"{base_oid}.3"
    print(f"   Testing OID: {test_oid}")
    
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(test_oid)),
        )
        
        print(f"   Error indication: {error_indication}")
        print(f"   Error status: {error_status}")
        
        if not error_indication and not error_status and var_binds:
            for name, val in var_binds:
                print(f"   Response: name={name}, value={val}, type={type(val)}")
                
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    try:
                        # Check if it's a numeric value (power reading)
                        power_value = int(val)
                        discovered_sensors.append(1)  # Use index 1 as a flag
                        print(f"   ✅ Found power sensor! Value: {power_value} W")
                        print(f"   Integration will use discovered_sensors: [1]")
                    except (ValueError, TypeError) as e:
                        print(f"   ❌ Value is not numeric: {val} (error: {e})")
                else:
                    print(f"   ❌ No object at this OID")
    except Exception as exc:
        print(f"   ❌ Exception: {exc}")
    
    # Also test legacy indices 1-10
    print(f"\n2️⃣ Checking legacy indices 1-10:")
    for index in range(1, 11):
        test_oid = f"{base_oid}.{index}"
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(test_oid)),
            )
            
            if not error_indication and not error_status and var_binds:
                for name, val in var_binds:
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        # For power consumption, check for numeric values
                        try:
                            power_value = int(val)
                            discovered_sensors.append(index)
                            print(f"   Index {index}: {power_value} W ✅")
                        except (ValueError, TypeError):
                            # Check if it's a descriptive name with power keywords
                            val_str = str(val).strip()
                            if val_str and any(keyword in val_str for keyword in ["Power", "Current", "Consumption", "PS"]):
                                discovered_sensors.append(index)
                                print(f"   Index {index}: '{val_str}' (power-related) ✅")
                            else:
                                print(f"   Index {index}: '{val_str}' (non-power)")
        except Exception as exc:
            continue
    
    engine.close()
    
    print(f"\n📊 Discovery Result:")
    print(f"   discovered_sensors = {discovered_sensors}")
    if discovered_sensors:
        print(f"   ✅ Power discovery successful!")
        print(f"   Integration will store: discovered_power_consumption: {discovered_sensors}")
    else:
        print(f"   ❌ No power sensors discovered")
        print(f"   Integration will store: discovered_power_consumption: []")
    
    return discovered_sensors

async def test_actual_power_oids(host: str, community: str = "public"):
    """Test the actual power consumption OIDs"""
    print(f"\n🔌 Testing Actual Power OIDs")
    print("=" * 60)
    
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport = UdpTransportTarget((host, 161))
    context = ContextData()
    
    # These are the OIDs the integration uses to collect power data
    oids = {
        "power_consumption_current": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3",
        "power_consumption_peak": "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3",
    }
    
    power_data = {}
    
    for name, oid in oids.items():
        print(f"\nTesting {name}:")
        print(f"  OID: {oid}")
        
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                auth_data,
                transport,
                context,
                ObjectType(ObjectIdentity(oid))
            )
            
            if error_indication:
                print(f"  ❌ Error: {error_indication}")
            elif error_status:
                print(f"  ❌ Error: {error_status}")
            else:
                for var_name, var_value in var_binds:
                    if str(var_value) != "No Such Object currently exists at this OID":
                        try:
                            watts = int(var_value)
                            print(f"  ✅ Value: {watts} W")
                            power_data[name] = watts
                        except:
                            print(f"  ❌ Non-numeric value: {var_value}")
                    else:
                        print(f"  ❌ OID not found")
        except Exception as e:
            print(f"  ❌ Exception: {e}")
    
    engine.close()
    
    if power_data:
        print(f"\n✅ Power monitoring is working!")
        print(f"   Current: {power_data.get('power_consumption_current', 'N/A')} W")
        print(f"   Peak: {power_data.get('power_consumption_peak', 'N/A')} W")
    else:
        print(f"\n❌ Power monitoring not available via SNMP")
    
    return bool(power_data)

async def main(host: str, community: str = "public"):
    """Main test function"""
    print(f"🔧 POWER SENSOR DISCOVERY TEST")
    print(f"Host: {host}")
    print(f"Community: {community}")
    print("=" * 60)
    
    # Test discovery logic
    discovered = await test_discovery_logic(host, community)
    
    # Test actual power OIDs
    power_available = await test_actual_power_oids(host, community)
    
    # Analysis
    print(f"\n📊 FINAL ANALYSIS")
    print("=" * 60)
    
    if power_available and not discovered:
        print("❌ PROBLEM IDENTIFIED!")
        print("   Power data IS available but discovery is failing")
        print("\n   This suggests the discovery logic has a bug.")
        print("   The integration is looking for power data at the wrong OID during discovery.")
        print("\n   WORKAROUND: You may need to manually patch the discovery")
        print("   or the integration needs to be fixed.")
    elif power_available and discovered:
        print("✅ Discovery should work correctly")
        print("   If sensors still don't appear, check:")
        print("   1. Config entry has the discovered data")
        print("   2. SNMP coordinator is processing the data")
        print("   3. Sensor creation logic is working")
    else:
        print("❓ Power monitoring may not be supported on this iDRAC")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 test_power_discovery_detailed.py <idrac_ip> [community]")
        sys.exit(1)
    
    HOST = sys.argv[1]
    COMMUNITY = sys.argv[2] if len(sys.argv) > 2 else "public"
    
    asyncio.run(main(HOST, COMMUNITY))