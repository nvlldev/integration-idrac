#!/usr/bin/env python3
"""
Purpose: Debug script to diagnose intrusion detection sensor issues
Usage: python tests/debug_intrusion.py (uses .env.local or .env.test)
Requirements: python-dotenv, pysnmp
Author: Claude Code Assistant  
Date: 2025-01-28
"""
import asyncio
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    # Load environment variables (.env.local preferred, .env.test fallback)
    load_dotenv('.env.local')
    load_dotenv('.env.test')
except ImportError:
    print("Warning: python-dotenv not installed. Using command line arguments only.")
    load_dotenv = None
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

# SNMP OIDs for intrusion detection
INTRUSION_OIDS = {
    "location": "1.3.6.1.4.1.674.10892.5.4.300.70.1.8.1",
    "reading": "1.3.6.1.4.1.674.10892.5.4.300.70.1.6.1",
    "status": "1.3.6.1.4.1.674.10892.5.4.300.70.1.5.1",
}

async def test_intrusion_sensor(host: str, community: str = "public", port: int = 161):
    """Test intrusion sensor discovery."""
    engine = SnmpEngine()
    auth_data = CommunityData(community)
    transport_target = UdpTransportTarget((host, port))
    context_data = ContextData()
    
    print(f"\nTesting intrusion sensors on {host}:{port}")
    print("=" * 60)
    
    # Test indices 1-5
    for index in range(1, 6):
        print(f"\nTesting index {index}:")
        
        for oid_name, base_oid in INTRUSION_OIDS.items():
            test_oid = f"{base_oid}.{index}"
            
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    for name, val in var_binds:
                        if val is not None and str(val) != "No Such Object currently exists at this OID":
                            print(f"  {oid_name}: {val} (OID: {test_oid})")
                        else:
                            print(f"  {oid_name}: No object at this OID")
                else:
                    if error_indication:
                        print(f"  {oid_name}: Error - {error_indication}")
                    elif error_status:
                        print(f"  {oid_name}: Error - {error_status.prettyPrint()}")
                        
            except Exception as exc:
                print(f"  {oid_name}: Exception - {exc}")
    
    engine.close()

if __name__ == "__main__":
    # Get configuration from environment files or command line
    if len(sys.argv) > 1:
        HOST = sys.argv[1]
        COMMUNITY = sys.argv[2] if len(sys.argv) > 2 else "public"
        PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 161
    else:
        # Get from environment variables
        HOST = os.getenv('IDRAC_HOST')
        COMMUNITY = os.getenv('IDRAC_COMMUNITY', 'public')
        PORT = int(os.getenv('IDRAC_PORT', '161'))
    
    if not HOST:
        print("Error: Please provide iDRAC host via:")
        print("  1. Command line: python tests/debug_intrusion.py <host> [community] [port]")
        print("  2. Environment: Configure IDRAC_HOST in .env.local or .env.test")
        sys.exit(1)
    
    print(f"Testing intrusion sensors on {HOST}:{PORT} with community '{COMMUNITY}'")
    print(f"Usage: {sys.argv[0]} [host] [community] [port]")
    
    asyncio.run(test_intrusion_sensor(HOST, COMMUNITY, PORT))