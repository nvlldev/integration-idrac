#!/usr/bin/env python3
"""Test script to validate Dell iDRAC voltage OIDs."""

import asyncio
import os
import sys
from pathlib import Path
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')
    else:
        print(f"No .env file found at {env_file}")
        print("Create a .env file with:")
        print("IDRAC_HOST=192.168.1.100")
        print("IDRAC_COMMUNITY=public")
        print("IDRAC_PORT=161")


async def test_voltage_oids(host: str, community: str = "public", port: int = 161):
    """Test specific voltage OIDs and discover working indices."""
    engine = SnmpEngine()
    community_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
    context_data = ContextData()

    # Base OID for voltage probes
    base_oid = "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1"
    
    print(f"Testing Dell iDRAC voltage OIDs on {host}:{port}")
    print(f"Base OID: {base_oid}")
    print("=" * 60)

    # Test specific indices from the example (26, 27)
    example_indices = [26, 27]
    print("Testing example indices from online configuration:")
    for index in example_indices:
        test_oid = f"{base_oid}.{index}"
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(test_oid)),
            )

            if error_indication:
                print(f"  Index {index:2d}: ERROR - {error_indication}")
            elif error_status:
                print(f"  Index {index:2d}: ERROR - {error_status}")
            elif var_binds:
                value = var_binds[0][1]
                if (value is not None 
                    and str(value) != "No Such Object currently exists at this OID"
                    and str(value) != "No Such Instance currently exists at this OID"):
                    try:
                        voltage_mv = int(value)
                        voltage_v = voltage_mv / 1000.0
                        print(f"  Index {index:2d}: {voltage_mv} mV ({voltage_v:.3f} V) ✓")
                    except (ValueError, TypeError):
                        print(f"  Index {index:2d}: Non-numeric value: {value}")
                else:
                    print(f"  Index {index:2d}: No data available")
            else:
                print(f"  Index {index:2d}: No response")

        except Exception as exc:
            print(f"  Index {index:2d}: Exception - {exc}")

    print("\n" + "=" * 60)
    print("Scanning for other voltage probe indices (1-40):")
    
    found_indices = []
    
    # Scan a broader range to find all available voltage probes
    for index in range(1, 41):
        test_oid = f"{base_oid}.{index}"
        try:
            error_indication, error_status, error_index, var_binds = await getCmd(
                engine,
                community_data,
                transport_target,
                context_data,
                ObjectType(ObjectIdentity(test_oid)),
            )

            if not error_indication and not error_status and var_binds:
                value = var_binds[0][1]
                if (value is not None 
                    and str(value) != "No Such Object currently exists at this OID"
                    and str(value) != "No Such Instance currently exists at this OID"):
                    try:
                        voltage_mv = int(value)
                        voltage_v = voltage_mv / 1000.0
                        print(f"  Index {index:2d}: {voltage_mv} mV ({voltage_v:.3f} V) ✓")
                        found_indices.append(index)
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        pass

        except Exception:
            # Skip errors during scanning
            pass

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Found {len(found_indices)} voltage probe indices: {found_indices}")
    
    if found_indices:
        print("\nSuggested OID configuration:")
        for i, index in enumerate(found_indices, 1):
            print(f"PSU {i} Voltage OID: {base_oid}.{index}")
        
        print("\nHome Assistant SNMP sensor configuration:")
        for i, index in enumerate(found_indices, 1):
            print(f"""  - platform: snmp
    host: {host}
    port: {port}
    community: {community}
    name: PSU_{i}_Voltage
    baseoid: {base_oid}.{index}
    unit_of_measurement: V
    value_template: "{{{{((value | float) / 1000) | float}}}}"
""")
    else:
        print("No voltage probes found. Voltage monitoring may not be available on this iDRAC.")

    print("=" * 60)


async def main():
    """Main function."""
    # Load environment variables
    load_env_file()
    
    # Get parameters from command line args or environment variables
    if len(sys.argv) >= 2:
        # Command line arguments provided
        host = sys.argv[1]
        community = sys.argv[2] if len(sys.argv) > 2 else "public"
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 161
    else:
        # Try to get from environment variables
        host = os.getenv('IDRAC_HOST')
        community = os.getenv('IDRAC_COMMUNITY', 'public')
        port = int(os.getenv('IDRAC_PORT', '161'))
        
        if not host:
            print("Usage: python test_voltage_oids.py <host> [community] [port]")
            print("   OR: Set IDRAC_HOST, IDRAC_COMMUNITY, IDRAC_PORT in .env file")
            print("\nExample command line:")
            print("python test_voltage_oids.py 192.168.1.100 public 161")
            print("\nExample .env file:")
            print("IDRAC_HOST=192.168.1.100")
            print("IDRAC_COMMUNITY=public")
            print("IDRAC_PORT=161")
            sys.exit(1)
    
    print(f"Testing iDRAC at {host}:{port} with community '{community}'")
    await test_voltage_oids(host, community, port)


if __name__ == "__main__":
    asyncio.run(main())