#!/usr/bin/env python3
"""Test script to verify device info OIDs work with your iDRAC."""

import asyncio
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

# Update these with your iDRAC details
IDRAC_HOST = "YOUR_IDRAC_IP"
IDRAC_PORT = 161
COMMUNITY = "public"

# Device info OIDs to test
TEST_OIDS = {
    "system_model_name": "1.3.6.1.4.1.674.10892.5.1.3.12.0",
    "system_model_name_alt": "1.3.6.1.4.1.674.10892.5.4.300.10.1.9.1.1",
    "system_model_name_alt2": "1.3.6.1.4.1.674.10892.5.4.300.10.1.7.1.1",
    "system_service_tag": "1.3.6.1.4.1.674.10892.5.1.3.2.0",
    "system_bios_version": "1.3.6.1.4.1.674.10892.5.1.3.6.0",
    "cpu_brand": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.23.1.1",
    "cpu_max_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.11.1.1",
    "cpu_current_speed": "1.3.6.1.4.1.674.10892.5.4.1100.30.1.12.1.1",
}

async def test_snmp_oid(engine, community_data, transport_target, context_data, name, oid):
    """Test a single SNMP OID."""
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid)),
        )

        if error_indication:
            print(f"❌ {name}: SNMP error indication: {error_indication}")
            return None
        
        if error_status:
            print(f"❌ {name}: SNMP error status: {error_status}")
            return None

        if var_binds:
            value = var_binds[0][1]
            value_str = str(value).strip()
            if value_str and "No Such Object" not in value_str and "No Such Instance" not in value_str:
                print(f"✅ {name}: {value_str}")
                return value_str
            else:
                print(f"❌ {name}: No valid data ({value_str})")
                return None
        else:
            print(f"❌ {name}: No response data")
            return None

    except Exception as exc:
        print(f"❌ {name}: Exception: {exc}")
        return None

async def main():
    """Test all device info OIDs."""
    print(f"Testing device info OIDs on {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 60)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    results = {}
    
    for name, oid in TEST_OIDS.items():
        print(f"\nTesting {name} ({oid}):")
        result = await test_snmp_oid(engine, community_data, transport_target, context_data, name, oid)
        results[name] = result
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    
    # System info
    print(f"Model: {results.get('system_model_name') or results.get('system_model_name_alt') or results.get('system_model_name_alt2') or 'Not found'}")
    print(f"Service Tag: {results.get('system_service_tag') or 'Not found'}")
    print(f"BIOS Version: {results.get('system_bios_version') or 'Not found'}")
    print(f"CPU Brand: {results.get('cpu_brand') or 'Not found'}")
    
    # CPU speeds
    max_speed = results.get('cpu_max_speed')
    current_speed = results.get('cpu_current_speed')
    if max_speed:
        try:
            max_ghz = float(max_speed) / 1000
            print(f"CPU Max Speed: {max_speed} MHz ({max_ghz:.2f} GHz)")
        except:
            print(f"CPU Max Speed: {max_speed}")
    else:
        print("CPU Max Speed: Not found")
    
    if current_speed:
        try:
            current_ghz = float(current_speed) / 1000
            print(f"CPU Current Speed: {current_speed} MHz ({current_ghz:.2f} GHz)")
        except:
            print(f"CPU Current Speed: {current_speed}")
    else:
        print("CPU Current Speed: Not found")

if __name__ == "__main__":
    print("Please update IDRAC_HOST and COMMUNITY variables before running this script!")
    print("Then run: python3 test_device_info_oids.py")
    # Uncomment the next line after updating the variables above
    # asyncio.run(main())