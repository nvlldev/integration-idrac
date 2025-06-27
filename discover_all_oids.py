#!/usr/bin/env python3
"""Comprehensive SNMP walk script to discover ALL available OIDs on Dell iDRAC."""

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
    nextCmd,
)

# Load environment variables
load_dotenv()

IDRAC_HOST = os.getenv("IDRAC_HOST")
IDRAC_PORT = int(os.getenv("IDRAC_PORT", "161"))
COMMUNITY = os.getenv("IDRAC_COMMUNITY", "public")

if not IDRAC_HOST:
    print("❌ Error: IDRAC_HOST not found in .env file")
    exit(1)

# Dell OID branches to explore comprehensively
DELL_OID_BRANCHES = {
    # Core Dell enterprise OID
    "Dell Root": "1.3.6.1.4.1.674",
    
    # Main iDRAC subtrees
    "iDRAC Base": "1.3.6.1.4.1.674.10892",
    "iDRAC v5": "1.3.6.1.4.1.674.10892.5",
    
    # System Information
    "System Info": "1.3.6.1.4.1.674.10892.5.1",
    "System Details": "1.3.6.1.4.1.674.10892.5.1.3",
    
    # Hardware Monitoring
    "Hardware": "1.3.6.1.4.1.674.10892.5.4",
    "System State": "1.3.6.1.4.1.674.10892.5.4.200",
    "Chassis": "1.3.6.1.4.1.674.10892.5.4.300",
    "Power Supply": "1.3.6.1.4.1.674.10892.5.4.600",
    "Cooling": "1.3.6.1.4.1.674.10892.5.4.700",
    "Processors": "1.3.6.1.4.1.674.10892.5.4.1100",
    "Memory": "1.3.6.1.4.1.674.10892.5.4.1100.50",
    
    # Storage
    "Storage": "1.3.6.1.4.1.674.10892.5.5",
    "Storage Details": "1.3.6.1.4.1.674.10892.5.5.1.20",
    
    # Network
    "Network": "1.3.6.1.4.1.674.10892.5.3",
    
    # Remote Access
    "Remote Access": "1.3.6.1.4.1.674.10892.5.2",
}

# Results storage
all_discovered_oids = {}
categorized_oids = {
    "model_names": [],
    "versions": [],
    "temperatures": [],
    "fans": [],
    "power": [],
    "voltage": [],
    "current": [],
    "memory": [],
    "storage": [],
    "network": [],
    "status": [],
    "health": [],
    "control": [],
    "other": []
}

async def walk_oid_subtree(engine, community_data, transport_target, context_data, name, base_oid, max_results=500):
    """Walk an OID subtree and collect all available OIDs."""
    print(f"\n🔍 Walking {name} ({base_oid})...")
    results = []
    count = 0
    
    try:
        # Use nextCmd to walk the entire subtree
        error_indication, error_status, error_index, var_binds = None, None, None, None
        
        # Create iterator manually since asyncio support varies
        current_oid = ObjectIdentity(base_oid)
        
        while count < max_results:
            try:
                # Get next OID in tree
                error_indication, error_status, error_index, var_binds = await nextCmd(
                    engine,
                    community_data,
                    transport_target,
                    context_data,
                    ObjectType(current_oid),
                    lexicographicMode=False,
                    maxRows=1
                ).__anext__()
                
                if error_indication or error_status:
                    break
                
                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    value = str(var_bind[1])
                    
                    # Check if we're still in the target subtree
                    if not oid_str.startswith(base_oid):
                        return results
                    
                    # Skip empty or error values
                    if not value or "No Such" in value:
                        continue
                    
                    # Store the result
                    oid_data = {
                        "oid": oid_str,
                        "value": value[:200] + "..." if len(value) > 200 else value,  # Truncate very long values
                        "type": type(var_bind[1]).__name__,
                        "branch": name
                    }
                    results.append(oid_data)
                    count += 1
                    
                    # Print interesting findings immediately
                    if count % 50 == 0:
                        print(f"   📍 Found {count} OIDs...")
                    
                    # Update current OID for next iteration
                    current_oid = ObjectIdentity(oid_str)
                    
                    # Check for interesting keywords in OID or value
                    interesting_keywords = ['name', 'model', 'version', 'temp', 'fan', 'power', 'volt', 'current', 'memory', 'disk', 'health', 'status', 'speed']
                    if any(keyword in oid_str.lower() or keyword in value.lower() for keyword in interesting_keywords):
                        print(f"     🔸 {oid_str}: {value[:80]}{'...' if len(value) > 80 else ''}")
            
            except StopAsyncIteration:
                break
            except Exception as e:
                break
    
    except Exception as e:
        print(f"   ❌ Error walking {name}: {e}")
    
    print(f"   ✅ Found {len(results)} OIDs in {name}")
    all_discovered_oids[name] = results
    return results

def categorize_oid(oid_data):
    """Categorize an OID based on its path and value."""
    oid = oid_data["oid"].lower()
    value = oid_data["value"].lower()
    
    # Categorization rules
    if any(keyword in oid or keyword in value for keyword in ['model', 'name', 'product', 'manufacturer']):
        categorized_oids["model_names"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['version', 'revision', 'bios', 'firmware']):
        categorized_oids["versions"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['temp', 'thermal']):
        categorized_oids["temperatures"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['fan', 'cooling']):
        categorized_oids["fans"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['power', 'watt', 'psu']):
        categorized_oids["power"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['volt', 'voltage']):
        categorized_oids["voltage"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['current', 'amp', 'amperage']):
        categorized_oids["current"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['memory', 'dimm', 'ram']):
        categorized_oids["memory"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['storage', 'disk', 'raid', 'controller']):
        categorized_oids["storage"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['network', 'nic', 'ethernet']):
        categorized_oids["network"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['status', 'state']):
        categorized_oids["status"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['health', 'condition']):
        categorized_oids["health"].append(oid_data)
    elif any(keyword in oid or keyword in value for keyword in ['control', 'command', 'action']):
        categorized_oids["control"].append(oid_data)
    else:
        categorized_oids["other"].append(oid_data)

async def main():
    """Main function to perform comprehensive OID discovery."""
    print(f"🚀 COMPREHENSIVE DELL iDRAC OID DISCOVERY")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 80)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=15, retries=2)
    context_data = ContextData()

    # Walk each OID branch
    print("🌳 Walking Dell iDRAC OID tree...")
    
    for branch_name, base_oid in DELL_OID_BRANCHES.items():
        results = await walk_oid_subtree(engine, community_data, transport_target, context_data, branch_name, base_oid, max_results=300)
        
        # Categorize the results
        for oid_data in results:
            categorize_oid(oid_data)
    
    # Analyze and display results
    print(f"\n" + "=" * 80)
    print("📊 DISCOVERY ANALYSIS")
    print("=" * 80)
    
    total_oids = sum(len(results) for results in all_discovered_oids.values())
    print(f"Total OIDs discovered: {total_oids}")
    
    print(f"\n📋 OIDs by Branch:")
    for branch_name, results in all_discovered_oids.items():
        print(f"   {branch_name}: {len(results)} OIDs")
    
    print(f"\n🏷️ OIDs by Category:")
    for category, oids in categorized_oids.items():
        if oids:
            print(f"   {category.replace('_', ' ').title()}: {len(oids)} OIDs")
    
    # Display interesting findings by category
    print(f"\n" + "=" * 80)
    print("🔍 INTERESTING FINDINGS BY CATEGORY")
    print("=" * 80)
    
    for category, oids in categorized_oids.items():
        if oids and len(oids) <= 50:  # Only show categories with reasonable number of OIDs
            print(f"\n🏷️ {category.replace('_', ' ').title()} ({len(oids)} OIDs):")
            print("-" * 50)
            for oid_data in oids[:20]:  # Show first 20 of each category
                print(f"   {oid_data['oid']}: {oid_data['value']}")
            if len(oids) > 20:
                print(f"   ... and {len(oids) - 20} more")
    
    # Save comprehensive results to files
    print(f"\n" + "=" * 80)
    print("💾 SAVING RESULTS")
    print("=" * 80)
    
    # Save to JSON
    with open("all_discovered_oids.json", "w") as f:
        json.dump({
            "summary": {
                "total_oids": total_oids,
                "branches": {name: len(results) for name, results in all_discovered_oids.items()},
                "categories": {name: len(oids) for name, oids in categorized_oids.items()}
            },
            "by_branch": all_discovered_oids,
            "by_category": categorized_oids
        }, f, indent=2)
    print("✅ Saved detailed results to: all_discovered_oids.json")
    
    # Save to CSV for easy analysis
    with open("all_discovered_oids.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["OID", "Value", "Type", "Branch", "Category"])
        
        for branch_name, results in all_discovered_oids.items():
            for oid_data in results:
                # Find category for this OID
                category = "other"
                for cat_name, cat_oids in categorized_oids.items():
                    if oid_data in cat_oids:
                        category = cat_name
                        break
                
                writer.writerow([
                    oid_data["oid"],
                    oid_data["value"],
                    oid_data["type"],
                    oid_data["branch"],
                    category
                ])
    print("✅ Saved CSV for analysis to: all_discovered_oids.csv")
    
    # Create a focused report of potentially useful OIDs
    print("\n📋 Creating focused report...")
    
    useful_oids = []
    for category in ["model_names", "versions", "temperatures", "fans", "power", "voltage", "current", "memory", "storage", "health", "status"]:
        useful_oids.extend(categorized_oids[category])
    
    with open("useful_oids_report.txt", "w") as f:
        f.write(f"DELL iDRAC USEFUL OIDs REPORT\n")
        f.write(f"Generated for: {IDRAC_HOST}:{IDRAC_PORT}\n")
        f.write(f"Total useful OIDs found: {len(useful_oids)}\n")
        f.write("=" * 80 + "\n\n")
        
        for category in ["model_names", "versions", "temperatures", "fans", "power", "voltage", "current", "memory", "storage", "health", "status"]:
            if categorized_oids[category]:
                f.write(f"\n{category.replace('_', ' ').upper()} ({len(categorized_oids[category])} OIDs):\n")
                f.write("-" * 50 + "\n")
                for oid_data in categorized_oids[category]:
                    f.write(f"{oid_data['oid']}: {oid_data['value']}\n")
    
    print("✅ Saved focused report to: useful_oids_report.txt")
    
    # Summary of actionable findings
    print(f"\n" + "=" * 80)
    print("🎯 ACTIONABLE FINDINGS")
    print("=" * 80)
    
    # Look for potential improvements to our integration
    new_model_oids = [oid for oid in categorized_oids["model_names"] if "model" in oid["oid"].lower() or "name" in oid["oid"].lower()]
    new_version_oids = [oid for oid in categorized_oids["versions"] if "version" in oid["oid"].lower() or "bios" in oid["oid"].lower()]
    new_voltage_oids = [oid for oid in categorized_oids["voltage"] if len(oid["value"]) < 10]  # Likely numeric values
    new_control_oids = [oid for oid in categorized_oids["control"]]
    
    if new_model_oids:
        print(f"\n🏷️ Potential Model Name OIDs ({len(new_model_oids)} found):")
        for oid in new_model_oids[:5]:
            print(f"   {oid['oid']}: {oid['value']}")
    
    if new_version_oids:
        print(f"\n📋 Potential Version OIDs ({len(new_version_oids)} found):")
        for oid in new_version_oids[:5]:
            print(f"   {oid['oid']}: {oid['value']}")
    
    if new_voltage_oids:
        print(f"\n⚡ Potential Voltage Sensor OIDs ({len(new_voltage_oids)} found):")
        for oid in new_voltage_oids[:5]:
            print(f"   {oid['oid']}: {oid['value']}")
    
    if new_control_oids:
        print(f"\n🎛️ Potential Control OIDs ({len(new_control_oids)} found):")
        for oid in new_control_oids[:5]:
            print(f"   {oid['oid']}: {oid['value']}")
    
    print(f"\n🎉 Discovery complete! Found {total_oids} total OIDs across {len(DELL_OID_BRANCHES)} branches.")
    print(f"📁 Results saved to multiple files for analysis.")

if __name__ == "__main__":
    print("Dell iDRAC Comprehensive OID Discovery Tool")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Community: {COMMUNITY}")
    asyncio.run(main())