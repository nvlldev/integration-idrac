#!/usr/bin/env python3
"""SNMP walk script to discover available Dell iDRAC OIDs."""

import asyncio
import os
import sys
from dotenv import load_dotenv
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    nextCmd,
)

# Load environment variables
load_dotenv()

# Get configuration from .env file
IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

if not IDRAC_HOST:
    print("❌ Error: IDRAC_HOST not found in .env file")
    sys.exit(1)

# Dell OID branches to explore
DELL_OID_BRANCHES = {
    "Dell Root": "1.3.6.1.4.1.674",
    "System Information": "1.3.6.1.4.1.674.10892.5.1.3",
    "Chassis Information": "1.3.6.1.4.1.674.10892.5.4.300",
    "Power Management": "1.3.6.1.4.1.674.10892.5.4.600",
    "Cooling": "1.3.6.1.4.1.674.10892.5.4.700",
    "Processors": "1.3.6.1.4.1.674.10892.5.4.1100",
    "Memory": "1.3.6.1.4.1.674.10892.5.4.1100.50",
    "Storage": "1.3.6.1.4.1.674.10892.5.5.1.20",
    "System State": "1.3.6.1.4.1.674.10892.5.4.200",
}

# Results storage
discovered_oids = {}

async def walk_oid_branch(engine, community_data, transport_target, context_data, branch_name, base_oid, max_results=100):
    """Walk an OID branch and collect all available OIDs."""
    print(f"\n🔍 Walking {branch_name} ({base_oid})...")
    results = []
    count = 0
    
    try:
        iterator = nextCmd(
            engine,
            community_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=1
        )
        
        while count < max_results:
            try:
                error_indication, error_status, error_index, var_binds = await iterator.__anext__()
                
                if error_indication or error_status:
                    break
                
                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    value = str(var_bind[1])
                    
                    # Check if we're still in the target branch
                    if not oid_str.startswith(base_oid):
                        return results
                    
                    # Skip empty or error values
                    if value and "No Such" not in value:
                        results.append({
                            "oid": oid_str,
                            "value": value[:100] + "..." if len(value) > 100 else value,  # Truncate long values
                            "type": type(var_bind[1]).__name__
                        })
                        count += 1
                        
                        # Print interesting findings immediately
                        if any(keyword in oid_str.lower() for keyword in ['model', 'name', 'version', 'power', 'state', 'status']):
                            print(f"   📍 {oid_str}: {value[:50]}{'...' if len(value) > 50 else ''}")
            
            except StopAsyncIteration:
                break
            except Exception as e:
                print(f"   ⚠️  Error during walk: {e}")
                break
    
    except Exception as e:
        print(f"   ❌ Failed to walk {branch_name}: {e}")
    
    print(f"   ✅ Found {len(results)} OIDs in {branch_name}")
    discovered_oids[branch_name] = results
    return results

async def search_for_missing_sensors(all_results):
    """Search through discovered OIDs for missing sensors."""
    print(f"\n🔍 SEARCHING FOR MISSING SENSORS")
    print("=" * 60)
    
    # Combine all results
    all_oids = []
    for branch_results in all_results.values():
        all_oids.extend(branch_results)
    
    # Search patterns for missing sensors
    search_patterns = {
        "Model/Chassis Names": ["model", "chassis", "name", "product"],
        "BIOS/Firmware": ["bios", "firmware", "version"],
        "Power State": ["power", "state", "status"],
        "Intrusion Detection": ["intrusion", "security", "breach", "tamper"],
        "Voltage Sensors": ["voltage", "volt"],
        "Memory Health": ["memory", "dimm", "ram"],
        "PSU Redundancy": ["redundancy", "redundant"],
        "LED Control": ["led", "identify", "beacon"],
        "System Control": ["control", "reset", "reboot"],
    }
    
    findings = {}
    
    for category, keywords in search_patterns.items():
        print(f"\n🔍 {category}:")
        category_findings = []
        
        for oid_data in all_oids:
            oid = oid_data["oid"]
            value = oid_data["value"]
            
            # Check if any keyword matches the OID or value
            if any(keyword in oid.lower() or keyword in value.lower() for keyword in keywords):
                category_findings.append(oid_data)
                print(f"   📍 {oid}: {value}")
        
        if not category_findings:
            print(f"   ❌ No OIDs found for {category}")
        
        findings[category] = category_findings
    
    return findings

async def test_candidate_oids(engine, community_data, transport_target, context_data, findings):
    """Test promising candidate OIDs for missing sensors."""
    print(f"\n🧪 TESTING CANDIDATE OIDS")
    print("=" * 60)
    
    from pysnmp.hlapi.asyncio import getCmd
    
    # Test some promising candidates
    candidates = {
        "Model Names": [
            "1.3.6.1.4.1.674.10892.5.1.3.12",  # Try without .0
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.9.1",  # Try without .1
            "1.3.6.1.4.1.674.10892.5.4.300.10.1.7.1",  # Try without .1
        ],
        "BIOS Version": [
            "1.3.6.1.4.1.674.10892.5.1.3.6",   # Try without .0
            "1.3.6.1.4.1.674.10892.5.1.3.5.0", # Try different index
            "1.3.6.1.4.1.674.10892.5.1.3.7.0", # Try different index
        ],
        "Power State": [
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.1",  # Different index
            "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.2",  # Different index
            "1.3.6.1.4.1.674.10892.5.4.200.10.1.6.1",    # System state power
        ],
        "Memory Health": [
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.4",  # Original (column 4)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.6",  # Try column 6
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20", # Try column 20
        ],
        "Voltage Sensors": [
            "1.3.6.1.4.1.674.10892.5.4.600.20.1.6",      # Try without index
            "1.3.6.1.4.1.674.10892.5.4.600.20.1.5.1",    # Try status instead
            "1.3.6.1.4.1.674.10892.5.4.700.10.1.6.1",    # Try different base
        ]
    }
    
    for category, test_oids in candidates.items():
        print(f"\n🧪 Testing {category}:")
        for oid in test_oids:
            # Test both with and without common indices
            test_variations = [oid + ".0", oid + ".1", oid + ".1.1", oid]
            
            for test_oid in test_variations:
                try:
                    error_indication, error_status, error_index, var_binds = await getCmd(
                        engine,
                        community_data,
                        transport_target,
                        context_data,
                        ObjectType(ObjectIdentity(test_oid)),
                    )

                    if not error_indication and not error_status and var_binds:
                        value = str(var_binds[0][1]).strip()
                        if value and "No Such" not in value:
                            print(f"   ✅ {test_oid}: {value}")
                        
                except Exception as e:
                    continue

async def main():
    """Main function to perform SNMP discovery."""
    print(f"🚀 SNMP Discovery on Dell iDRAC {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 80)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    # Walk each OID branch
    all_results = {}
    for branch_name, base_oid in DELL_OID_BRANCHES.items():
        results = await walk_oid_branch(engine, community_data, transport_target, context_data, branch_name, base_oid, max_results=50)
        all_results[branch_name] = results
    
    # Search for missing sensors
    findings = await search_for_missing_sensors(all_results)
    
    # Test candidate OIDs
    await test_candidate_oids(engine, community_data, transport_target, context_data, findings)
    
    # Print summary
    print(f"\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    
    total_oids = sum(len(results) for results in all_results.values())
    print(f"Total OIDs discovered: {total_oids}")
    
    for branch_name, results in all_results.items():
        print(f"{branch_name}: {len(results)} OIDs")
    
    print(f"\n💾 Results saved to discovered_oids variable for further analysis")
    
    # Save interesting findings to a file
    with open("snmp_discovery_results.txt", "w") as f:
        f.write(f"SNMP Discovery Results for {IDRAC_HOST}\n")
        f.write("=" * 50 + "\n\n")
        
        for branch_name, results in all_results.items():
            f.write(f"\n{branch_name} ({len(results)} OIDs):\n")
            f.write("-" * 40 + "\n")
            for oid_data in results:
                f.write(f"{oid_data['oid']}: {oid_data['value']}\n")
    
    print(f"📁 Detailed results saved to snmp_discovery_results.txt")

if __name__ == "__main__":
    print("Dell iDRAC SNMP Discovery Tool")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Community: {COMMUNITY}")
    asyncio.run(main())