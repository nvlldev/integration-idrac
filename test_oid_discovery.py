#!/usr/bin/env python3
"""Test script for Dell iDRAC SNMP OID discovery."""

import logging
import os
from dotenv import load_dotenv

try:
    # Try the synchronous imports first
    from pysnmp.hlapi.v1arch.syncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
        nextCmd,
    )
    SYNC_MODE = True
except ImportError:
    # Fall back to asyncio imports
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
    SYNC_MODE = False
    import asyncio

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# iDRAC connection details from environment
IDRAC_HOST = os.getenv('IDRAC_HOST')
IDRAC_PORT = int(os.getenv('IDRAC_PORT', '161'))
IDRAC_COMMUNITY = os.getenv('IDRAC_COMMUNITY', 'public')

# Known Dell iDRAC OIDs to test
TEST_OIDS = {
    'power': '1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3',
    'temp_inlet': '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.1',
    'temp_outlet': '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.2',
    'fan_base': '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1',
    'temp_base': '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1',
}

# Alternative OIDs to test
ALTERNATIVE_OIDS = {
    'fans': [
        '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1',  # Primary
        '1.3.6.1.4.1.674.10892.5.4.700.12.1.3.1',  # Alternative 1
        '1.3.6.1.4.1.674.10892.1.700.12.1.6.1',    # Alternative 2
        '1.3.6.1.4.1.674.10892.5.4.700.12.1.7.1',  # Alternative 3 (RPM reading)
    ],
    'temperatures': [
        '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1',  # Primary
        '1.3.6.1.4.1.674.10892.5.4.700.20.1.3.1',  # Alternative 1
        '1.3.6.1.4.1.674.10892.1.700.20.1.6.1',    # Alternative 2
        '1.3.6.1.4.1.674.10892.5.4.700.20.1.7.1',  # Alternative 3 (temperature reading)
    ],
}


def test_single_oid(engine, community_data, transport_target, context_data, oid, description):
    """Test a single OID to see if it returns a value."""
    try:
        logger.info(f"Testing {description} - OID: {oid}")
        
        error_indication, error_status, error_index, var_binds = next(
            getCmd(engine, community_data, transport_target, context_data,
                   ObjectType(ObjectIdentity(oid)))
        )
        
        if error_indication:
            logger.warning(f"  ❌ Error indication: {error_indication}")
            return False
        elif error_status:
            logger.warning(f"  ❌ Error status: {error_status}")
            return False
        else:
            value = var_binds[0][1]
            logger.info(f"  ✅ Success: {value}")
            return True
            
    except Exception as exc:
        logger.error(f"  ❌ Exception: {exc}")
        return False


def discover_sensors(engine, community_data, transport_target, context_data, base_oid, sensor_type):
    """Discover sensors by walking the SNMP tree."""
    logger.info(f"🔍 Discovering {sensor_type} sensors - Base OID: {base_oid}")
    results = []
    
    try:
        walk_count = 0
        for error_indication, error_status, error_index, var_binds in nextCmd(
            engine, community_data, transport_target, context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=50,
        ):
            if error_indication or error_status:
                logger.debug(f"  Walk ended - indication: {error_indication}, status: {error_status}")
                break
            
            walk_count += 1
            for var_bind in var_binds:
                oid_str = str(var_bind[0])
                value = var_bind[1]
                logger.debug(f"  Found: {oid_str} = {value}")
                
                if oid_str.startswith(f"{base_oid}."):
                    try:
                        sensor_id = int(oid_str.split(".")[-1])
                        if value is not None:
                            results.append((sensor_id, oid_str, value))
                            logger.info(f"  📊 Sensor ID {sensor_id}: {value}")
                    except (ValueError, IndexError):
                        logger.debug(f"  ⚠️  Could not parse sensor ID from: {oid_str}")
        
        logger.info(f"  📈 Found {len(results)} {sensor_type} sensors after {walk_count} iterations")
        return results
        
    except Exception as exc:
        logger.error(f"  ❌ Discovery error: {exc}")
        return []


def main():
    """Main test function."""
    if not IDRAC_HOST:
        logger.error("❌ IDRAC_HOST not set in environment variables!")
        return
    
    logger.info(f"🚀 Starting Dell iDRAC SNMP Discovery Test")
    logger.info(f"📡 Target: {IDRAC_HOST}:{IDRAC_PORT}")
    logger.info(f"🔑 Community: {IDRAC_COMMUNITY}")
    logger.info("=" * 60)
    
    # Setup SNMP engine
    engine = SnmpEngine()
    community_data = CommunityData(IDRAC_COMMUNITY)
    transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
    context_data = ContextData()
    
    # Test basic connectivity with known OIDs
    logger.info("📋 Testing Known OIDs:")
    for name, oid in TEST_OIDS.items():
        test_single_oid(engine, community_data, transport_target, context_data, oid, name)
    
    print()
    
    # Test fan sensor discovery
    logger.info("🌪️  TESTING FAN SENSOR DISCOVERY:")
    print("=" * 60)
    for i, oid in enumerate(ALTERNATIVE_OIDS['fans'], 1):
        logger.info(f"Attempt {i}/{len(ALTERNATIVE_OIDS['fans'])}")
        fans = discover_sensors(engine, community_data, transport_target, context_data, oid, "fan")
        if fans:
            logger.info(f"  🎯 SUCCESS! Found fans with OID: {oid}")
            for sensor_id, full_oid, value in fans:
                logger.info(f"    Fan {sensor_id}: {value} RPM (OID: {full_oid})")
            break
        else:
            logger.warning(f"  ❌ No fans found with OID: {oid}")
        print()
    
    print()
    
    # Test temperature sensor discovery
    logger.info("🌡️  TESTING TEMPERATURE SENSOR DISCOVERY:")
    print("=" * 60)
    for i, oid in enumerate(ALTERNATIVE_OIDS['temperatures'], 1):
        logger.info(f"Attempt {i}/{len(ALTERNATIVE_OIDS['temperatures'])}")
        temps = discover_sensors(engine, community_data, transport_target, context_data, oid, "temperature")
        if temps:
            logger.info(f"  🎯 SUCCESS! Found temperatures with OID: {oid}")
            for sensor_id, full_oid, value in temps:
                temp_celsius = float(value) / 10 if sensor_id > 2 else float(value) / 10
                sensor_type = "CPU" if sensor_id > 2 else ("Inlet" if sensor_id == 1 else "Outlet")
                logger.info(f"    {sensor_type} Temp {sensor_id}: {temp_celsius}°C (OID: {full_oid})")
            break
        else:
            logger.warning(f"  ❌ No temperatures found with OID: {oid}")
        print()
    
    logger.info("✅ Discovery test completed!")


if __name__ == "__main__":
    main()