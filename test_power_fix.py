#!/usr/bin/env python3
"""Test script to verify the power consumption OID fix."""

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

async def test_power_oids():
    """Test both power OIDs to verify which is real-time vs capacity."""
    print("🔌 Testing Power Consumption OIDs")
    print("=" * 50)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test both power OIDs
    power_oids = [
        ("Real-time power consumption", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"),   # Should be ~140W
        ("Maximum power capacity", "1.3.6.1.4.1.674.10892.5.4.600.30.1.10.1.3"),      # Should be 644W  
        ("Power warning threshold", "1.3.6.1.4.1.674.10892.5.4.600.30.1.11.1.3"),     # Should be 588W
    ]
    
    for name, oid in power_oids:
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
                    print(f"   ✅ {name}: {value}W")
                else:
                    print(f"   ❌ {name}: No data")
            else:
                print(f"   ❌ {name}: SNMP error")
        except Exception as e:
            print(f"   ❌ {name}: Error - {e}")
    
    print("\n💡 Expected results:")
    print("   - Real-time power consumption: ~140W (actual current usage)")
    print("   - Maximum power capacity: 644W (total PSU capacity or max)")
    print("   - Power warning threshold: 588W (threshold for warnings)")

async def main():
    """Main test function."""
    await test_power_oids()

if __name__ == "__main__":
    asyncio.run(main())