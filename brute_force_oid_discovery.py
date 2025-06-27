#!/usr/bin/env python3
"""Brute force OID discovery script for Dell iDRAC - tests ranges of OIDs systematically."""

import asyncio
import os
import json
import csv
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

if not IDRAC_HOST:
    print("❌ Error: IDRAC_HOST not found in .env file")
    exit(1)

# Define OID patterns to test systematically
OID_PATTERNS = {
    # System Information patterns
    "System Info Base": {
        "base": "1.3.6.1.4.1.674.10892.5.1.3",
        "test_range": range(1, 50),  # Test .1 through .50
        "suffixes": [".0", ""]  # Test both with and without .0
    },
    
    # Hardware monitoring patterns  
    "System State": {
        "base": "1.3.6.1.4.1.674.10892.5.4.200.10.1",
        "test_range": range(1, 100),
        "suffixes": [".1", ".0", ""]
    },
    
    # Chassis patterns
    "Chassis Status": {
        "base": "1.3.6.1.4.1.674.10892.5.4.300.10.1",
        "test_range": range(1, 30),
        "suffixes": [".1.1", ".1", ".0", ""]
    },
    
    "Chassis Power": {
        "base": "1.3.6.1.4.1.674.10892.5.4.300.70.1",
        "test_range": range(1, 50),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    # Power Supply patterns
    "PSU Management": {
        "base": "1.3.6.1.4.1.674.10892.5.4.600.10.1",
        "test_range": range(1, 30),
        "suffixes": [".1.1", ".1.2", ".1", ".0", ""]
    },
    
    "PSU Status": {
        "base": "1.3.6.1.4.1.674.10892.5.4.600.12.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    "PSU Voltage": {
        "base": "1.3.6.1.4.1.674.10892.5.4.600.20.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    "PSU Current": {
        "base": "1.3.6.1.4.1.674.10892.5.4.600.30.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    # Cooling patterns
    "Cooling Devices": {
        "base": "1.3.6.1.4.1.674.10892.5.4.700.10.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    "Fan Speed": {
        "base": "1.3.6.1.4.1.674.10892.5.4.700.12.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    "Temperature Probes": {
        "base": "1.3.6.1.4.1.674.10892.5.4.700.20.1",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1", ".0", ""]
    },
    
    # Processor patterns
    "Processor Status": {
        "base": "1.3.6.1.4.1.674.10892.5.4.1100.30.1",
        "test_range": range(1, 50),
        "suffixes": [".1.1", ".1.2", ".1", ".0", ""]
    },
    
    # Memory patterns
    "Memory Device": {
        "base": "1.3.6.1.4.1.674.10892.5.4.1100.50.1",
        "test_range": range(1, 30),
        "suffixes": [".1.1", ".1.2", ".1.3", ".1.4", ".1.5", ".1.6", ".1.7", ".1.8", ".1", ".0", ""]
    },
    
    # Storage patterns  
    "Storage Controller": {
        "base": "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1",
        "test_range": range(1, 50),
        "suffixes": [".1", ".0", ""]
    },
    
    "Virtual Disk": {
        "base": "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1",
        "test_range": range(1, 30),
        "suffixes": [".1", ".0", ""]
    },
    
    "Physical Disk": {
        "base": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1",
        "test_range": range(1, 30),
        "suffixes": [".1", ".2", ".3", ".4", ".5", ".0", ""]
    },
    
    # Remote Access patterns
    "Remote Access": {
        "base": "1.3.6.1.4.1.674.10892.5.2",
        "test_range": range(1, 20),
        "suffixes": [".0", ""]
    },
    
    # Network patterns
    "Network Interface": {
        "base": "1.3.6.1.4.1.674.10892.5.3",
        "test_range": range(1, 20),
        "suffixes": [".1.1", ".1", ".0", ""]
    }
}

# Results storage
discovered_oids = []
working_oids_by_pattern = {}

async def test_oid(engine, community_data, transport_target, context_data, oid):
    """Test a single OID and return the result."""
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
            if value and "No Such" not in value and value != "":
                return {
                    "oid": oid,
                    "value": value[:200] + "..." if len(value) > 200 else value,
                    "type": type(var_binds[0][1]).__name__
                }
        return None
    except Exception:
        return None

async def test_oid_pattern(engine, community_data, transport_target, context_data, pattern_name, pattern_config):
    """Test all OIDs in a pattern systematically."""
    print(f"\n🔍 Testing {pattern_name}...")
    base = pattern_config["base"]
    test_range = pattern_config["test_range"]
    suffixes = pattern_config["suffixes"]
    
    working_oids = []
    total_tests = len(test_range) * len(suffixes)
    tested = 0
    
    for i in test_range:
        for suffix in suffixes:
            oid = f"{base}.{i}{suffix}"
            result = await test_oid(engine, community_data, transport_target, context_data, oid)
            tested += 1
            
            if result:
                working_oids.append(result)
                discovered_oids.append(result)
                print(f"   ✅ {oid}: {result['value'][:80]}{'...' if len(result['value']) > 80 else ''}")
            
            # Progress indicator
            if tested % 50 == 0:
                print(f"   📍 Tested {tested}/{total_tests} OIDs...")
    
    working_oids_by_pattern[pattern_name] = working_oids
    print(f"   ✅ Found {len(working_oids)} working OIDs in {pattern_name}")
    return working_oids

def categorize_discoveries():
    """Categorize discovered OIDs by content."""
    categories = {
        "system_info": [],
        "hardware_status": [],
        "temperatures": [],
        "fans": [],
        "power": [],
        "voltage": [],
        "current": [],
        "memory": [],
        "storage": [],
        "network": [],
        "versions": [],
        "names_models": [],
        "control": [],
        "other": []
    }
    
    for oid_data in discovered_oids:
        oid = oid_data["oid"].lower()
        value = oid_data["value"].lower()
        
        # Categorization logic
        if any(keyword in oid or keyword in value for keyword in ['model', 'name', 'product', 'manufacturer', 'chassis']):
            categories["names_models"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['version', 'revision', 'bios', 'firmware']):
            categories["versions"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['temp', 'thermal']) or '.700.20.' in oid:
            categories["temperatures"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['fan', 'cooling']) or '.700.12.' in oid:
            categories["fans"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['power', 'watt']) or '.600.30.' in oid:
            categories["power"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['volt', 'voltage']) or '.600.20.' in oid:
            categories["voltage"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['current', 'amp', 'amperage']):
            categories["current"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['memory', 'dimm', 'ram']) or '.1100.50.' in oid:
            categories["memory"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['storage', 'disk', 'raid', 'controller']) or '.5.5.1.20.' in oid:
            categories["storage"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['network', 'nic', 'ethernet']) or '.5.3.' in oid:
            categories["network"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['status', 'state', 'health', 'condition']):
            categories["hardware_status"].append(oid_data)
        elif any(keyword in oid or keyword in value for keyword in ['control', 'command', 'action', 'set']):
            categories["control"].append(oid_data)
        elif '.5.1.3.' in oid:
            categories["system_info"].append(oid_data)
        else:
            categories["other"].append(oid_data)
    
    return categories

async def main():
    """Main function to perform systematic OID discovery."""
    print(f"🚀 SYSTEMATIC DELL iDRAC OID DISCOVERY")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Testing {len(OID_PATTERNS)} OID patterns...")
    print("=" * 80)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    # Test each OID pattern
    for pattern_name, pattern_config in OID_PATTERNS.items():
        await test_oid_pattern(engine, community_data, transport_target, context_data, pattern_name, pattern_config)
    
    # Categorize results
    categories = categorize_discoveries()
    
    # Display results
    print(f"\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    
    total_discovered = len(discovered_oids)
    print(f"Total working OIDs discovered: {total_discovered}")
    
    print(f"\n📋 Working OIDs by Pattern:")
    for pattern_name, oids in working_oids_by_pattern.items():
        if oids:
            print(f"   {pattern_name}: {len(oids)} OIDs")
    
    print(f"\n🏷️ Working OIDs by Category:")
    for category, oids in categories.items():
        if oids:
            print(f"   {category.replace('_', ' ').title()}: {len(oids)} OIDs")
    
    # Display interesting findings
    print(f"\n" + "=" * 80)
    print("🔍 INTERESTING FINDINGS")
    print("=" * 80)
    
    # Show most useful categories
    useful_categories = ["names_models", "versions", "temperatures", "fans", "power", "voltage", "memory", "storage", "hardware_status"]
    
    for category in useful_categories:
        if categories[category]:
            print(f"\n🏷️ {category.replace('_', ' ').title()} ({len(categories[category])} OIDs):")
            print("-" * 50)
            for oid_data in categories[category][:15]:  # Show first 15
                print(f"   {oid_data['oid']}: {oid_data['value']}")
            if len(categories[category]) > 15:
                print(f"   ... and {len(categories[category]) - 15} more")
    
    # Save results
    print(f"\n" + "=" * 80)
    print("💾 SAVING RESULTS")
    print("=" * 80)
    
    # Save comprehensive JSON
    results = {
        "summary": {
            "total_discovered": total_discovered,
            "patterns_tested": len(OID_PATTERNS),
            "target": f"{IDRAC_HOST}:{IDRAC_PORT}"
        },
        "by_pattern": working_oids_by_pattern,
        "by_category": categories,
        "all_oids": discovered_oids
    }
    
    with open("systematic_oid_discovery.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ Saved detailed results to: systematic_oid_discovery.json")
    
    # Save CSV
    with open("systematic_oid_discovery.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["OID", "Value", "Type", "Category"])
        
        for oid_data in discovered_oids:
            # Find category
            category = "other"
            for cat_name, cat_oids in categories.items():
                if oid_data in cat_oids:
                    category = cat_name
                    break
            
            writer.writerow([oid_data["oid"], oid_data["value"], oid_data["type"], category])
    
    print("✅ Saved CSV for analysis to: systematic_oid_discovery.csv")
    
    # Create actionable report
    with open("actionable_oids_report.txt", "w") as f:
        f.write(f"DELL iDRAC ACTIONABLE OIDs REPORT\n")
        f.write(f"Target: {IDRAC_HOST}:{IDRAC_PORT}\n")
        f.write(f"Total OIDs discovered: {total_discovered}\n")
        f.write("=" * 80 + "\n\n")
        
        # Potential improvements for integration
        f.write("POTENTIAL INTEGRATION IMPROVEMENTS:\n")
        f.write("-" * 40 + "\n\n")
        
        if categories["names_models"]:
            f.write("NEW MODEL NAME OIDs:\n")
            for oid_data in categories["names_models"]:
                f.write(f"   {oid_data['oid']}: {oid_data['value']}\n")
            f.write("\n")
        
        if categories["versions"]:
            f.write("NEW VERSION OIDs:\n")
            for oid_data in categories["versions"]:
                f.write(f"   {oid_data['oid']}: {oid_data['value']}\n")
            f.write("\n")
        
        if categories["voltage"]:
            f.write("VOLTAGE SENSOR OIDs:\n")
            for oid_data in categories["voltage"]:
                f.write(f"   {oid_data['oid']}: {oid_data['value']}\n")
            f.write("\n")
        
        if categories["control"]:
            f.write("CONTROL OIDs:\n")
            for oid_data in categories["control"]:
                f.write(f"   {oid_data['oid']}: {oid_data['value']}\n")
            f.write("\n")
    
    print("✅ Saved actionable report to: actionable_oids_report.txt")
    
    print(f"\n🎉 Systematic discovery complete!")
    print(f"Found {total_discovered} working OIDs across {len(OID_PATTERNS)} patterns.")

if __name__ == "__main__":
    print("Dell iDRAC Systematic OID Discovery Tool")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Community: {COMMUNITY}")
    asyncio.run(main())