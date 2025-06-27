#!/usr/bin/env python3
"""Comprehensive test to output all sensor values for comparison with iDRAC interface."""

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

async def get_snmp_value(engine, community_data, transport_target, context_data, oid):
    """Get a single SNMP value."""
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
                return value
        return None
    except Exception:
        return None

async def test_all_sensors():
    """Test all sensors and output current values."""
    print("🔍 COMPREHENSIVE DELL iDRAC SENSOR TEST")
    print(f"Target: {IDRAC_HOST}:{IDRAC_PORT}")
    print("=" * 80)
    
    engine = SnmpEngine()
    community_data = CommunityData(COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
    context_data = ContextData()
    
    # System Information
    print("\n📋 SYSTEM INFORMATION")
    print("-" * 40)
    system_oids = [
        ("System Service Tag", "1.3.6.1.4.1.674.10892.5.1.3.2.0"),
        ("System Model Name", "1.3.6.1.4.1.674.10892.5.4.300.10.1.7.1"),
        ("System Manufacturer", "1.3.6.1.4.1.674.10892.5.4.300.10.1.8.1"),
        ("System Power State", "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1.1"),
    ]
    
    for name, oid in system_oids:
        value = await get_snmp_value(engine, community_data, transport_target, context_data, oid)
        print(f"   {name}: {value}")
    
    # Temperature Sensors
    print("\n🌡️ TEMPERATURE SENSORS")
    print("-" * 40)
    temp_indices = [1, 2, 3]  # Inlet, Exhaust, CPU temps
    temp_names = [
        "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.1",  # System Board Inlet Temp
        "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.2",  # System Board Exhaust Temp  
        "1.3.6.1.4.1.674.10892.5.4.700.20.1.8.1.3",  # CPU1 Temp
    ]
    
    for i, name_oid in zip(temp_indices, temp_names):
        temp_oid = f"1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.{i}"
        name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        temp_value = await get_snmp_value(engine, community_data, transport_target, context_data, temp_oid)
        if temp_value:
            temp_celsius = int(temp_value) / 10 if temp_value.isdigit() else temp_value
            print(f"   {name}: {temp_celsius}°C")
    
    # Fan Sensors
    print("\n🌀 FAN SENSORS")
    print("-" * 40)
    fan_indices = [1, 2, 3]
    fan_names = [
        "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.1",  # System Board Fan1
        "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.2",  # System Board Fan2
        "1.3.6.1.4.1.674.10892.5.4.700.12.1.8.1.3",  # System Board Fan3
    ]
    
    for i, name_oid in zip(fan_indices, fan_names):
        fan_oid = f"1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.{i}"
        name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        fan_value = await get_snmp_value(engine, community_data, transport_target, context_data, fan_oid)
        print(f"   {name}: {fan_value} RPM")
    
    # Power Supply Sensors
    print("\n⚡ POWER SUPPLY SENSORS")
    print("-" * 40)
    psu_indices = [1, 2]
    for i in psu_indices:
        psu_name = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.600.12.1.8.1.{i}")
        psu_status = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.600.12.1.5.1.{i}")
        psu_voltage = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.600.12.1.4.1.{i}")
        psu_max_output = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.600.12.1.6.1.{i}")
        
        status_map = {1: "other", 2: "unknown", 3: "ok", 4: "non_critical", 5: "critical", 6: "non_recoverable"}
        status_text = status_map.get(int(psu_status) if psu_status and psu_status.isdigit() else 0, "unknown")
        
        print(f"   {psu_name}:")
        print(f"      Status: {status_text} (code: {psu_status})")
        print(f"      Input Voltage: {psu_voltage}V")
        print(f"      Max Output: {psu_max_output}W")
    
    # Power Consumption
    print("\n🔌 POWER CONSUMPTION")
    print("-" * 40)
    power_oids = [
        ("Real-time System Power", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3", "W"),
        ("PSU1 Current", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.1", "A"),
        ("PSU2 Current", "1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.2", "A"),
        ("Total System Power", "1.3.6.1.4.1.674.10892.5.4.600.30.1.10.1.3", "W"),
        ("Power Warning Threshold", "1.3.6.1.4.1.674.10892.5.4.600.30.1.11.1.3", "W"),
    ]
    
    for name, oid, unit in power_oids:
        value = await get_snmp_value(engine, community_data, transport_target, context_data, oid)
        print(f"   {name}: {value}{unit}")
    
    # System Voltages
    print("\n⚡ SYSTEM VOLTAGES")
    print("-" * 40)
    voltage_oids = [
        ("CPU1 VCORE", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.1", "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.1"),
        ("CPU2 VCORE", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.2", "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.2"),
        ("System 3.3V", "1.3.6.1.4.1.674.10892.5.4.600.20.1.16.1.3", "1.3.6.1.4.1.674.10892.5.4.600.20.1.8.1.3"),
    ]
    
    for label, status_oid, name_oid in voltage_oids:
        status = await get_snmp_value(engine, community_data, transport_target, context_data, status_oid)
        name = await get_snmp_value(engine, community_data, transport_target, context_data, name_oid)
        status_text = "OK" if status == "1" else f"Problem (code: {status})"
        print(f"   {name}: {status_text}")
    
    # Memory Health
    print("\n🧠 MEMORY HEALTH")
    print("-" * 40)
    memory_indices = [1, 2, 3, 4, 5, 6, 7, 8]
    memory_health_map = {1: "other", 2: "ready", 3: "ok", 4: "non_critical", 5: "critical", 6: "non_recoverable"}
    
    for i in memory_indices:
        health_oid = f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.4.1.{i}"
        location_oid = f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1.{i}"
        size_oid = f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.14.1.{i}"
        speed_oid = f"1.3.6.1.4.1.674.10892.5.4.1100.50.1.27.1.{i}"
        
        health = await get_snmp_value(engine, community_data, transport_target, context_data, health_oid)
        location = await get_snmp_value(engine, community_data, transport_target, context_data, location_oid)
        size = await get_snmp_value(engine, community_data, transport_target, context_data, size_oid)
        speed = await get_snmp_value(engine, community_data, transport_target, context_data, speed_oid)
        
        if health:
            health_text = memory_health_map.get(int(health) if health.isdigit() else 0, "unknown")
            size_gb = int(size) // 1024 // 1024 if size and size.isdigit() else "Unknown"
            print(f"   {location}: {health_text} (code: {health}) - {size_gb}GB @ {speed}MHz")
    
    # Processor Information
    print("\n🖥️ PROCESSOR INFORMATION")
    print("-" * 40)
    cpu_indices = [1, 2]
    for i in cpu_indices:
        cpu_brand = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.1100.30.1.23.1.{i}")
        cpu_current_speed = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.1100.30.1.12.1.{i}")
        cpu_max_speed = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.1100.30.1.11.1.{i}")
        cpu_status = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.4.1100.30.1.5.1.{i}")
        
        status_map = {1: "other", 2: "unknown", 3: "ok", 4: "non_critical", 5: "critical", 6: "non_recoverable"}
        status_text = status_map.get(int(cpu_status) if cpu_status and cpu_status.isdigit() else 0, "unknown")
        
        print(f"   CPU {i}: {cpu_brand}")
        print(f"      Status: {status_text}")
        print(f"      Current Speed: {cpu_current_speed}MHz")
        print(f"      Max Speed: {cpu_max_speed}MHz")
    
    # Storage Information
    print("\n💾 STORAGE INFORMATION")
    print("-" * 40)
    
    # Storage Controller
    controller_name = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.2.1")
    controller_firmware = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.8.1")
    controller_cache = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.9.1")
    controller_status = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.130.1.1.38.1")
    
    status_map = {1: "other", 2: "unknown", 3: "ok", 4: "non_critical", 5: "critical", 6: "non_recoverable"}
    controller_status_text = status_map.get(int(controller_status) if controller_status and controller_status.isdigit() else 0, "unknown")
    
    print(f"   Storage Controller: {controller_name}")
    print(f"      Status: {controller_status_text}")
    print(f"      Firmware: {controller_firmware}")
    print(f"      Cache Size: {controller_cache}MB")
    
    # Virtual Disks
    vdisk_name = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.2.1")
    vdisk_state = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.4.1")
    vdisk_size = await get_snmp_value(engine, community_data, transport_target, context_data, "1.3.6.1.4.1.674.10892.5.5.1.20.140.1.1.6.1")
    
    vdisk_state_map = {1: "ready", 2: "failed", 3: "online", 4: "offline", 5: "degraded"}
    vdisk_state_text = vdisk_state_map.get(int(vdisk_state) if vdisk_state and vdisk_state.isdigit() else 0, "unknown")
    
    print(f"   Virtual Disk: {vdisk_name}")
    print(f"      State: {vdisk_state_text}")
    print(f"      Size: {vdisk_size}MB")
    
    # Physical Disks
    disk_indices = [1, 2, 3, 4, 5]
    for i in disk_indices:
        disk_name = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.2.{i}")
        disk_vendor = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.3.{i}")
        disk_model = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.6.{i}")
        disk_size = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.11.{i}")
        disk_state = await get_snmp_value(engine, community_data, transport_target, context_data, f"1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1.4.{i}")
        
        if disk_name:
            disk_state_map = {1: "ready", 2: "failed", 3: "online", 4: "offline", 5: "degraded"}
            disk_state_text = disk_state_map.get(int(disk_state) if disk_state and disk_state.isdigit() else 0, "unknown")
            size_gb = int(disk_size) // 1024 if disk_size and disk_size.isdigit() else "Unknown"
            
            print(f"   {disk_name}: {disk_vendor} {disk_model}")
            print(f"      State: {disk_state_text}")
            print(f"      Size: {size_gb}GB")
    
    print("\n" + "=" * 80)
    print("✅ Test complete! Compare these values with your iDRAC interface.")
    print("🔍 Pay special attention to:")
    print("   - Temperature readings (should match iDRAC thermal section)")
    print("   - Real-time System Power (should match iDRAC power consumption)")
    print("   - Memory health status (should match iDRAC memory section)")
    print("   - Fan speeds (should match iDRAC cooling section)")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        print("❌ Error: IDRAC_HOST not found in .env file")
        return
    
    await test_all_sensors()

if __name__ == "__main__":
    asyncio.run(main())