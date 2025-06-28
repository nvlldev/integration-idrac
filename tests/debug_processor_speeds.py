#!/usr/bin/env python3
"""
Purpose: Debug script to diagnose processor speed sensor availability issues
Usage: python tests/debug_processor_speeds.py (uses .env.local or .env.test)
Requirements: python-dotenv, requests
Author: Claude Code Assistant
Date: 2025-01-28
"""
import asyncio
import logging
import os
import sys
import json

try:
    from dotenv import load_dotenv
    # Load environment variables (.env.local preferred, .env.test fallback)
    load_dotenv('.env.local')
    load_dotenv('.env.test')
except ImportError:
    print("Warning: python-dotenv not installed. Using command line arguments only.")
    load_dotenv = None

import requests
from requests.auth import HTTPBasicAuth
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

async def test_processor_speeds(host: str, username: str, password: str):
    """Test processor speed data retrieval from Redfish API."""
    base_url = f"https://{host}/redfish/v1"
    auth = HTTPBasicAuth(username, password)
    
    print(f"\nTesting processor speed data on {host}")
    print("=" * 80)
    
    try:
        # Get system information
        print("\n1. Fetching System information...")
        system_response = requests.get(
            f"{base_url}/Systems/System.Embedded.1",
            auth=auth,
            verify=False,
            timeout=30
        )
        
        if system_response.status_code == 200:
            system_data = system_response.json()
            
            # Check ProcessorSummary
            processor_summary = system_data.get("ProcessorSummary", {})
            print(f"ProcessorSummary found: {bool(processor_summary)}")
            
            if processor_summary:
                print(f"ProcessorSummary keys: {list(processor_summary.keys())}")
                print(f"Count: {processor_summary.get('Count')}")
                print(f"ProcessorCount: {processor_summary.get('ProcessorCount')}")
                print(f"Model: {processor_summary.get('Model')}")
                print(f"ProcessorModel: {processor_summary.get('ProcessorModel')}")
                print(f"MaxSpeedMHz: {processor_summary.get('MaxSpeedMHz')}")
                print(f"SpeedMHz: {processor_summary.get('SpeedMHz')}")
                print(f"Status: {processor_summary.get('Status')}")
                
                # Show full ProcessorSummary for debugging
                print(f"\nFull ProcessorSummary:")
                print(json.dumps(processor_summary, indent=2))
            else:
                print("No ProcessorSummary found in system data")
                
        else:
            print(f"Failed to get system data: {system_response.status_code}")
            print(f"Response: {system_response.text}")
            
        # Get detailed processor information
        print("\n2. Fetching detailed Processors collection...")
        processors_response = requests.get(
            f"{base_url}/Systems/System.Embedded.1/Processors",
            auth=auth,
            verify=False,
            timeout=30
        )
        
        if processors_response.status_code == 200:
            processors_data = processors_response.json()
            members = processors_data.get("Members", [])
            print(f"Found {len(members)} processor entries")
            
            for i, member in enumerate(members[:3]):  # Check first 3 processors
                processor_url = member.get("@odata.id", "")
                if processor_url:
                    print(f"\n  Processor {i+1}: {processor_url}")
                    
                    try:
                        proc_response = requests.get(
                            f"https://{host}{processor_url}",
                            auth=auth,
                            verify=False,
                            timeout=30
                        )
                        
                        if proc_response.status_code == 200:
                            proc_data = proc_response.json()
                            print(f"    Name: {proc_data.get('Name')}")
                            print(f"    Model: {proc_data.get('Model')}")
                            print(f"    MaxSpeedMHz: {proc_data.get('MaxSpeedMHz')}")
                            print(f"    CurrentSpeedMHz: {proc_data.get('CurrentSpeedMHz')}")
                            print(f"    SpeedMHz: {proc_data.get('SpeedMHz')}")
                            print(f"    Status: {proc_data.get('Status')}")
                        else:
                            print(f"    Failed to get processor details: {proc_response.status_code}")
                            
                    except Exception as exc:
                        print(f"    Exception getting processor details: {exc}")
        else:
            print(f"Failed to get processors collection: {processors_response.status_code}")
            
        # Summary
        print("\n3. Summary:")
        if system_response.status_code == 200:
            system_data = system_response.json()
            processor_summary = system_data.get("ProcessorSummary", {})
            
            max_speed = processor_summary.get("MaxSpeedMHz")
            current_speed = processor_summary.get("SpeedMHz")
            
            print(f"  - MaxSpeedMHz available: {max_speed is not None} ({'YES' if max_speed is not None else 'NO'})")
            print(f"  - SpeedMHz available: {current_speed is not None} ({'YES' if current_speed is not None else 'NO'})")
            
            if max_speed is None and current_speed is None:
                print("  - Speed sensors will show as unavailable")
                print("  - This iDRAC may not expose processor speed via ProcessorSummary")
                print("  - Individual processor endpoints may have the data instead")
            else:
                print("  - Speed sensors should be available")
        
    except Exception as exc:
        print(f"Exception during testing: {exc}")

if __name__ == "__main__":
    # Get configuration from environment files or command line
    if len(sys.argv) > 3:
        HOST = sys.argv[1]
        USERNAME = sys.argv[2]
        PASSWORD = sys.argv[3]
    else:
        # Get from environment variables
        HOST = os.getenv('IDRAC_HOST')
        USERNAME = os.getenv('IDRAC_USERNAME', 'root')
        PASSWORD = os.getenv('IDRAC_PASSWORD')
    
    if not HOST or not PASSWORD:
        print("Error: Please provide iDRAC credentials via:")
        print("  1. Command line: python tests/debug_processor_speeds.py <host> <username> <password>")
        print("  2. Environment: Configure IDRAC_HOST, IDRAC_USERNAME, IDRAC_PASSWORD in .env.local or .env.test")
        sys.exit(1)
    
    print(f"Testing processor speeds on {HOST} with user '{USERNAME}'")
    print(f"Usage: {sys.argv[0]} [host] [username] [password]")
    
    asyncio.run(test_processor_speeds(HOST, USERNAME, PASSWORD))