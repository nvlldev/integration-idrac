#!/usr/bin/env python3
"""Test PSU current scaling to fix the 10x error."""

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

load_dotenv()
IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

async def test_power_scaling():
    """Test different power current OIDs and scaling."""
    print("🔌 Testing PSU Current Scaling")
    print("=" * 40)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # Test raw current values and different scaling
    current_oids = [
        ("PSU1 Current Raw", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.1"),
        ("PSU2 Current Raw", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.2"),
        ("System Current Raw", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"),
        ("PSU1 Current Alt", "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.1"),
        ("PSU2 Current Alt", "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.2"),
        ("System Current Alt", "1.3.6.1.4.1.674.10892.5.4.600.30.1.7.1.3"),
    ]
    
    for name, oid in current_oids:
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine, community_data, transport_target, context_data,
                ObjectType(ObjectIdentity(oid))
            )
            
            if not error_indication and not error_status and var_binds:
                raw_value = str(var_binds[0][1]).strip()
                if raw_value and "No Such" not in raw_value and raw_value.isdigit():
                    raw_int = int(raw_value)
                    scaled_10 = raw_int / 10.0
                    scaled_100 = raw_int / 100.0
                    print(f"   {name}: {raw_value} raw → {scaled_10}A (/10) or {scaled_100}A (/100)")
                else:
                    print(f"   {name}: {raw_value}")
        except Exception as e:
            print(f"   {name}: Error - {e}")
    
    print("\n💡 Expected: PSU1=1.2A, PSU2=0.2A, System=140W")

if __name__ == "__main__":
    asyncio.run(test_power_scaling())