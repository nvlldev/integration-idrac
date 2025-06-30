#!/usr/bin/env python3
"""
Quick SNMP test script for Dell iDRAC
This script provides a quick way to test specific OIDs or do targeted discovery.
"""

import asyncio
import sys
import logging
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Common Dell iDRAC OIDs for quick testing
QUICK_TEST_OIDS = {
    "system_model": "1.3.6.1.4.1.674.10892.5.1.1.1.0",
    "system_tag": "1.3.6.1.4.1.674.10892.5.1.1.2.0",
    "system_name": "1.3.6.1.4.1.674.10892.5.1.1.3.0",
    
    # Temperature sensors (first few)
    "temp1_name": "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1",
    "temp1_reading": "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
    "temp1_state": "1.3.6.1.4.1.674.10892.5.4.700.20.1.5.1",
    
    # Fan sensors (first few)
    "fan1_name": "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1",
    "fan1_reading": "1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1",
    "fan1_state": "1.3.6.1.4.1.674.10892.5.4.700.12.1.5.1",
    
    # Power consumption
    "power1_name": "1.3.6.1.4.1.674.10892.5.4.600.30.1.8.1",
    "power1_reading": "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1",
    "power1_state": "1.3.6.1.4.1.674.10892.5.4.600.30.1.5.1",
    
    # Voltage sensors (first few)
    "voltage1_name": "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1",
    "voltage1_reading": "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1",
    "voltage1_state": "1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1",
}


async def test_single_oid(host: str, oid: str, community: str = "public") -> str:
    """Test a single OID."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, 161))
    context_data = ContextData()
    
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(oid)),
        )
        
        if error_indication:
            return f"Error: {error_indication}"
        elif error_status:
            return f"Error: {error_status.prettyPrint()}"
        else:
            for name, val in var_binds:
                if val is not None and str(val) != "No Such Object currently exists at this OID":
                    return str(val).strip()
                else:
                    return "No data"
                    
    except Exception as e:
        return f"Exception: {e}"
    finally:
        try:
            engine.observer.stop()
        except:
            pass
        
    return "Unknown error"


async def walk_oid(host: str, base_oid: str, community: str = "public", max_results: int = 20):
    """Walk an OID tree."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, 161))
    context_data = ContextData()
    
    results = []
    try:
        count = 0
        for (error_indication, error_status, error_index, var_binds) in await nextCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=max_results
        ):
            if error_indication:
                logger.error(f"Walk error: {error_indication}")
                break
            elif error_status:
                logger.error(f"Walk error: {error_status.prettyPrint()}")
                break
            else:
                for name, val in var_binds:
                    oid_str = str(name)
                    if oid_str.startswith(base_oid):
                        if val is not None and str(val) != "No Such Object currently exists at this OID":
                            results.append((oid_str, str(val).strip()))
                            count += 1
                            if count >= max_results:
                                return results
                    else:
                        return results
                        
    except Exception as e:
        logger.error(f"Exception during walk: {e}")
    finally:
        try:
            engine.observer.stop()
        except:
            pass
        
    return results


async def quick_test(host: str, community: str = "public"):
    """Run quick tests on common OIDs."""
    print(f"\nQuick SNMP test for {host}")
    print("="*50)
    
    for name, oid in QUICK_TEST_OIDS.items():
        result = await test_single_oid(host, oid, community)
        print(f"{name:20}: {result}")
        
    print("\nTemperature sensors walk:")
    temp_results = await walk_oid(host, "1.3.6.1.4.1.674.10892.5.4.700.20.1.8", community, 10)
    for oid, value in temp_results:
        print(f"  {oid}: {value}")
        
    print("\nFan sensors walk:")
    fan_results = await walk_oid(host, "1.3.6.1.4.1.674.10892.5.4.700.12.1.8", community, 10)
    for oid, value in fan_results:
        print(f"  {oid}: {value}")


async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python snmp_quick_test.py <host> [community]          - Quick test")
        print("  python snmp_quick_test.py <host> test <oid> [community] - Test single OID")
        print("  python snmp_quick_test.py <host> walk <base_oid> [community] - Walk OID tree")
        print("\nExamples:")
        print("  python snmp_quick_test.py 192.168.1.100")
        print("  python snmp_quick_test.py 192.168.1.100 test 1.3.6.1.4.1.674.10892.5.1.1.1.0")
        print("  python snmp_quick_test.py 192.168.1.100 walk 1.3.6.1.4.1.674.10892.5.4.700.20.1.8")
        sys.exit(1)
        
    host = sys.argv[1]
    
    if len(sys.argv) >= 3 and sys.argv[2] == "test":
        # Test single OID
        if len(sys.argv) < 4:
            print("Error: OID required for test command")
            sys.exit(1)
        oid = sys.argv[3]
        community = sys.argv[4] if len(sys.argv) > 4 else "public"
        
        print(f"Testing OID {oid} on {host}")
        result = await test_single_oid(host, oid, community)
        print(f"Result: {result}")
        
    elif len(sys.argv) >= 3 and sys.argv[2] == "walk":
        # Walk OID tree
        if len(sys.argv) < 4:
            print("Error: Base OID required for walk command")
            sys.exit(1)
        base_oid = sys.argv[3]
        community = sys.argv[4] if len(sys.argv) > 4 else "public"
        
        print(f"Walking OID tree {base_oid} on {host}")
        results = await walk_oid(host, base_oid, community, 50)
        if results:
            for oid, value in results:
                print(f"{oid}: {value}")
        else:
            print("No results found")
            
    else:
        # Quick test
        community = sys.argv[2] if len(sys.argv) > 2 else "public"
        await quick_test(host, community)


if __name__ == "__main__":
    asyncio.run(main())