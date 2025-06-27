#!/usr/bin/env python3
"""Comprehensive test script to verify all Dell iDRAC OIDs work correctly."""

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
    getCmd,
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

# Import the OIDs from the integration
sys.path.append(os.path.join(os.path.dirname(__file__), "custom_components", "idrac"))
from const import IDRAC_OIDS, SNMP_WALK_OIDS

# Test results storage
test_results = {
    "success": [],
    "failed": [],
    "discovery": {},
    "device_info": {}
}

async def test_snmp_oid(engine, community_data, transport_target, context_data, name, oid, expected_type="value"):
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
            test_results["failed"].append({"name": name, "oid": oid, "error": str(error_indication)})
            return None
        
        if error_status:
            print(f"❌ {name}: SNMP error status: {error_status}")
            test_results["failed"].append({"name": name, "oid": oid, "error": str(error_status)})
            return None

        if var_binds:
            value = var_binds[0][1]
            value_str = str(value).strip()
            
            if value_str and "No Such Object" not in value_str and "No Such Instance" not in value_str:
                # Format the output based on expected type
                if expected_type == "string":
                    print(f"✅ {name}: '{value_str}'")
                elif expected_type == "temperature":
                    try:
                        temp_val = float(value_str) / 10
                        print(f"✅ {name}: {temp_val}°C ({value_str} raw)")
                    except:
                        print(f"✅ {name}: {value_str}")
                elif expected_type == "frequency":
                    try:
                        freq_val = float(value_str)
                        freq_ghz = freq_val / 1000
                        print(f"✅ {name}: {freq_val} MHz ({freq_ghz:.2f} GHz)")
                    except:
                        print(f"✅ {name}: {value_str}")
                elif expected_type == "voltage":
                    try:
                        volt_val = float(value_str) / 1000
                        print(f"✅ {name}: {volt_val}V ({value_str} mV)")
                    except:
                        print(f"✅ {name}: {value_str}")
                elif expected_type == "amperage":
                    try:
                        amp_val = float(value_str) / 10
                        print(f"✅ {name}: {amp_val}A ({value_str} raw)")
                    except:
                        print(f"✅ {name}: {value_str}")
                else:
                    print(f"✅ {name}: {value_str}")
                
                test_results["success"].append({"name": name, "oid": oid, "value": value_str})
                return value_str
            else:
                print(f"❌ {name}: No valid data ({value_str})")
                test_results["failed"].append({"name": name, "oid": oid, "error": f"No valid data: {value_str}"})
                return None
        else:
            print(f"❌ {name}: No response data")
            test_results["failed"].append({"name": name, "oid": oid, "error": "No response data"})
            return None

    except Exception as exc:
        print(f"❌ {name}: Exception: {exc}")
        test_results["failed"].append({"name": name, "oid": oid, "error": str(exc)})
        return None

async def discover_indices(engine, community_data, transport_target, context_data, name, base_oid):
    """Discover available indices for a given base OID by testing common indices."""
    indices = []
    print(f"🔍 {name}: Testing common indices...")
    
    # Test common indices (1-20 for most sensor types)
    test_indices = range(1, 21)
    
    for test_index in test_indices:
        test_oid = f"{base_oid}.{test_index}"
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
                value_str = str(value).strip()
                if value_str and "No Such Object" not in value_str and "No Such Instance" not in value_str:
                    indices.append(test_index)
        except:
            continue
    
    print(f"🔍 {name}: Found indices {indices}")
    test_results["discovery"][name] = indices
    return indices

async def main():
    """Test all device info OIDs and discovered sensors."""
    print(f"🚀 Testing Dell iDRAC OIDs on {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 80)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()

    # Test system identification OIDs first
    print("\n📋 SYSTEM IDENTIFICATION")
    print("-" * 40)
    
    device_info_tests = [
        ("System Model Name", IDRAC_OIDS["system_model_name"], "string"),
        ("System Model Alt 1", IDRAC_OIDS["system_model_name_alt"], "string"),
        ("System Model Alt 2", IDRAC_OIDS["system_model_name_alt2"], "string"),
        ("Service Tag", IDRAC_OIDS["system_service_tag"], "string"),
        ("BIOS Version", IDRAC_OIDS["system_bios_version"], "string"),
        ("CPU Brand", IDRAC_OIDS["cpu_brand"], "string"),
        ("CPU Max Speed", IDRAC_OIDS["cpu_max_speed"], "frequency"),
        ("CPU Current Speed", IDRAC_OIDS["cpu_current_speed"], "frequency"),
    ]
    
    for name, oid, expected_type in device_info_tests:
        result = await test_snmp_oid(engine, community_data, transport_target, context_data, name, oid, expected_type)
        if result:
            test_results["device_info"][name] = result
    
    # Test basic monitoring OIDs
    print("\n⚡ BASIC MONITORING")
    print("-" * 40)
    
    basic_tests = [
        ("Power Consumption", IDRAC_OIDS["power"], "value"),
        ("Inlet Temperature", IDRAC_OIDS["temp_inlet"], "temperature"),
        ("Outlet Temperature", IDRAC_OIDS["temp_outlet"], "temperature"),
        ("System Health", IDRAC_OIDS["system_health"], "value"),
        ("System Power State", IDRAC_OIDS["system_power_state"], "value"),
        ("System Intrusion", IDRAC_OIDS["system_intrusion"], "value"),
        ("PSU Redundancy", IDRAC_OIDS["psu_redundancy"], "value"),
    ]
    
    for name, oid, expected_type in basic_tests:
        await test_snmp_oid(engine, community_data, transport_target, context_data, name, oid, expected_type)
    
    # Discover and test dynamic sensors
    print("\n🔍 DISCOVERY AND DYNAMIC SENSORS")
    print("-" * 40)
    
    # Discover CPU temperature sensors
    cpu_indices = await discover_indices(engine, community_data, transport_target, context_data, "CPU Temperature Sensors", SNMP_WALK_OIDS["cpu_temps"])
    for cpu_index in cpu_indices[:3]:  # Test first 3
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"CPU {cpu_index} Temperature", f"{IDRAC_OIDS['temp_cpu_base']}.{cpu_index}", "temperature")
    
    # Discover fan sensors
    fan_indices = await discover_indices(engine, community_data, transport_target, context_data, "Fan Sensors", SNMP_WALK_OIDS["fans"])
    for fan_index in fan_indices[:3]:  # Test first 3
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"Fan {fan_index} Speed", f"{IDRAC_OIDS['fan_base']}.{fan_index}", "value")
    
    # Discover PSU sensors
    psu_indices = await discover_indices(engine, community_data, transport_target, context_data, "PSU Status Sensors", SNMP_WALK_OIDS["psu_status"])
    for psu_index in psu_indices[:2]:  # Test first 2
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"PSU {psu_index} Status", f"{IDRAC_OIDS['psu_status_base']}.{psu_index}", "value")
    
    # Discover voltage sensors
    voltage_indices = await discover_indices(engine, community_data, transport_target, context_data, "Voltage Sensors", SNMP_WALK_OIDS["psu_voltage"])
    for voltage_index in voltage_indices[:2]:  # Test first 2
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"Voltage {voltage_index}", f"{IDRAC_OIDS['psu_voltage_base']}.{voltage_index}", "voltage")
    
    # Discover amperage sensors
    amperage_indices = await discover_indices(engine, community_data, transport_target, context_data, "Amperage Sensors", SNMP_WALK_OIDS["psu_amperage"])
    for amperage_index in amperage_indices[:2]:  # Test first 2
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"PSU {amperage_index} Amperage", f"{IDRAC_OIDS['psu_amperage_base']}.{amperage_index}", "amperage")
    
    # Discover memory sensors
    memory_indices = await discover_indices(engine, community_data, transport_target, context_data, "Memory Sensors", SNMP_WALK_OIDS["memory_health"])
    for memory_index in memory_indices[:3]:  # Test first 3
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"Memory {memory_index} Health", f"{IDRAC_OIDS['memory_health_base']}.{memory_index}", "value")
    
    # Test storage OIDs
    print("\n💾 STORAGE MONITORING")
    print("-" * 40)
    
    # Discover virtual disks
    vdisk_indices = await discover_indices(engine, community_data, transport_target, context_data, "Virtual Disks", SNMP_WALK_OIDS["virtual_disks"])
    for vdisk_index in vdisk_indices[:2]:  # Test first 2
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"VDisk {vdisk_index} State", f"{IDRAC_OIDS['virtual_disk_state']}.{vdisk_index}", "value")
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"VDisk {vdisk_index} Layout", f"{IDRAC_OIDS['virtual_disk_layout']}.{vdisk_index}", "value")
    
    # Discover physical disks
    pdisk_indices = await discover_indices(engine, community_data, transport_target, context_data, "Physical Disks", SNMP_WALK_OIDS["physical_disks"])
    for pdisk_index in pdisk_indices[:2]:  # Test first 2
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"PDisk {pdisk_index} State", f"{IDRAC_OIDS['physical_disk_state']}.{pdisk_index}", "value")
    
    # Discover storage controllers
    controller_indices = await discover_indices(engine, community_data, transport_target, context_data, "Storage Controllers", SNMP_WALK_OIDS["storage_controllers"])
    for controller_index in controller_indices:
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"Controller {controller_index} State", f"{IDRAC_OIDS['controller_state']}.{controller_index}", "value")
        await test_snmp_oid(engine, community_data, transport_target, context_data, f"Controller {controller_index} Battery", f"{IDRAC_OIDS['controller_battery_state']}.{controller_index}", "value")
    
    # Test control OIDs (read-only)
    print("\n🎛️  CONTROL OIDS (Read-Only Test)")
    print("-" * 40)
    
    control_tests = [
        ("Power Control OID", IDRAC_OIDS["power_control"]),
        ("Identify LED OID", IDRAC_OIDS["identify_led"]),
        ("Safe Mode OID", IDRAC_OIDS["safe_mode"]),
    ]
    
    for name, oid in control_tests:
        await test_snmp_oid(engine, community_data, transport_target, context_data, name, oid, "value")
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    print(f"✅ Successful tests: {len(test_results['success'])}")
    print(f"❌ Failed tests: {len(test_results['failed'])}")
    
    # Show device identification summary
    print(f"\n🏷️  DEVICE IDENTIFICATION:")
    device_info = test_results["device_info"]
    model = device_info.get("System Model Name") or device_info.get("System Model Alt 1") or device_info.get("System Model Alt 2") or "Not detected"
    service_tag = device_info.get("Service Tag", "Not detected")
    bios = device_info.get("BIOS Version", "Not detected")
    cpu_brand = device_info.get("CPU Brand", "Not detected")
    
    print(f"   Model: {model}")
    print(f"   Service Tag: {service_tag}")
    print(f"   BIOS: {bios}")
    print(f"   CPU: {cpu_brand}")
    
    # Show discovery summary
    print(f"\n🔍 DISCOVERY SUMMARY:")
    for sensor_type, indices in test_results["discovery"].items():
        if indices:
            print(f"   {sensor_type}: {len(indices)} found - {indices}")
        else:
            print(f"   {sensor_type}: None found")
    
    # Show failed tests
    if test_results["failed"]:
        print(f"\n❌ FAILED TESTS:")
        for failed in test_results["failed"]:
            print(f"   {failed['name']} ({failed['oid']}): {failed['error']}")
    
    print(f"\n🎯 Overall Success Rate: {len(test_results['success'])}/{len(test_results['success']) + len(test_results['failed'])} ({len(test_results['success'])/(len(test_results['success']) + len(test_results['failed']))*100:.1f}%)")

if __name__ == "__main__":
    print("Dell iDRAC OID Comprehensive Test")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print(f"Community: {COMMUNITY}")
    asyncio.run(main())