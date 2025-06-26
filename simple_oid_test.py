#!/usr/bin/env python3
"""Simple test script for Dell iDRAC SNMP OID discovery."""

import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import pysnmp - use whatever works
try:
    from pysnmp.hlapi.asyncio import *
    import asyncio
    ASYNC_MODE = True
    logger.info("Using asyncio mode")
except ImportError:
    logger.error("Could not import pysnmp")
    exit(1)

# iDRAC connection details from environment
IDRAC_HOST = os.getenv('IDRAC_HOST')
IDRAC_PORT = int(os.getenv('IDRAC_PORT', '161'))
IDRAC_COMMUNITY = os.getenv('IDRAC_COMMUNITY', 'public')

# Test OIDs - let's manually test some specific ones
TEST_OIDS = [
    ('Power', '1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3'),
    ('Inlet Temp', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.1'),
    ('Outlet Temp', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.2'),
    ('CPU Temp 1', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.3'),
    ('CPU Temp 2', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.4'),
    ('CPU Temp 3', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.5'),
    ('CPU Temp 4', '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1.6'),
    ('Fan 1 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.1'),
    ('Fan 2 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.2'),
    ('Fan 3 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.3'),
    ('Fan 4 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.4'),
    ('Fan 5 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.5'),
    ('Fan 6 Speed', '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1.6'),
]

async def test_single_oid_async(oid, description):
    """Test a single OID asynchronously."""
    try:
        engine = SnmpEngine()
        community_data = CommunityData(IDRAC_COMMUNITY)
        transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=5, retries=1)
        context_data = ContextData()
        
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine, community_data, transport_target, context_data,
            ObjectType(ObjectIdentity(oid))
        )
        
        if error_indication:
            logger.warning(f"❌ {description}: Error indication - {error_indication}")
            return None
        elif error_status:
            logger.warning(f"❌ {description}: Error status - {error_status}")
            return None
        else:
            value = var_binds[0][1]
            logger.info(f"✅ {description}: {value}")
            return value
            
    except Exception as exc:
        logger.error(f"❌ {description}: Exception - {exc}")
        return None

async def test_fan_walk_async():
    """Test walking the fan OID tree."""
    try:
        logger.info("🌪️  Walking fan OID tree...")
        engine = SnmpEngine()
        community_data = CommunityData(IDRAC_COMMUNITY)
        transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
        context_data = ContextData()
        
        base_oid = '1.3.6.1.4.1.674.10892.5.4.700.12.1.6.1'
        found_count = 0
        
        async for error_indication, error_status, error_index, var_binds in nextCmd(
            engine, community_data, transport_target, context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=20,
        ):
            if error_indication or error_status:
                logger.debug(f"Walk ended: {error_indication or error_status}")
                break
            
            for var_bind in var_binds:
                oid_str = str(var_bind[0])
                value = var_bind[1]
                
                if oid_str.startswith(f"{base_oid}."):
                    found_count += 1
                    logger.info(f"  📊 Found fan OID: {oid_str} = {value}")
        
        logger.info(f"📈 Found {found_count} fan entries")
        
    except Exception as exc:
        logger.error(f"❌ Fan walk error: {exc}")

async def test_temp_walk_async():
    """Test walking the temperature OID tree."""
    try:
        logger.info("🌡️  Walking temperature OID tree...")
        engine = SnmpEngine()
        community_data = CommunityData(IDRAC_COMMUNITY)
        transport_target = UdpTransportTarget((IDRAC_HOST, IDRAC_PORT), timeout=10, retries=2)
        context_data = ContextData()
        
        base_oid = '1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1'
        found_count = 0
        
        async for error_indication, error_status, error_index, var_binds in nextCmd(
            engine, community_data, transport_target, context_data,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
            maxRows=20,
        ):
            if error_indication or error_status:
                logger.debug(f"Walk ended: {error_indication or error_status}")
                break
            
            for var_bind in var_binds:
                oid_str = str(var_bind[0])
                value = var_bind[1]
                
                if oid_str.startswith(f"{base_oid}."):
                    found_count += 1
                    temp_c = float(value) / 10 if value else 0
                    logger.info(f"  📊 Found temp OID: {oid_str} = {value} ({temp_c}°C)")
        
        logger.info(f"📈 Found {found_count} temperature entries")
        
    except Exception as exc:
        logger.error(f"❌ Temperature walk error: {exc}")

async def main():
    """Main test function."""
    if not IDRAC_HOST:
        logger.error("❌ IDRAC_HOST not set in environment variables!")
        return
    
    logger.info(f"🚀 Starting Simple Dell iDRAC SNMP Test")
    logger.info(f"📡 Target: {IDRAC_HOST}:{IDRAC_PORT}")
    logger.info(f"🔑 Community: {IDRAC_COMMUNITY}")
    logger.info("=" * 60)
    
    # Test individual OIDs
    logger.info("📋 Testing Individual OIDs:")
    for description, oid in TEST_OIDS:
        await test_single_oid_async(oid, description)
    
    print()
    
    # Test SNMP walks
    await test_fan_walk_async()
    print()
    await test_temp_walk_async()
    
    logger.info("✅ Test completed!")

if __name__ == "__main__":
    if ASYNC_MODE:
        asyncio.run(main())
    else:
        logger.error("No working SNMP mode found")