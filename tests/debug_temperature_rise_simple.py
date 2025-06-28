#!/usr/bin/env python3
"""
Purpose: Simple debug script showing Temperature Rise sensor requirements
Usage: python tests/debug_temperature_rise_simple.py
Author: Claude Code Assistant
Date: 2025-01-28
"""

print("""
Temperature Rise Sensor Debug Information
==========================================

The Temperature Rise sensor requires BOTH inlet AND outlet temperature sensors
with specific naming patterns to be present in your system.

Required Patterns:
- INLET sensors: names containing "inlet", "intake", or "ambient"
- OUTLET sensors: names containing "outlet", "exhaust", or "exit"

If your system doesn't have temperature sensors with these exact naming patterns,
the Temperature Rise sensor will not be created.

Common Dell server temperature sensor names that DON'T match:
- "CPU 1 Temp"
- "System Board Temp" 
- "Memory Module Temp"
- "Chipset Temp"
- "PSU 1 Temp"

Example temperature sensor names that WOULD work:
- "System Inlet Temp" (inlet pattern)
- "System Outlet Temp" (outlet pattern)
- "Ambient Temp" (inlet pattern)
- "Exhaust Temp" (outlet pattern)

To check your actual temperature sensors:
1. Look in Home Assistant logs for temperature sensor discovery
2. Check the iDRAC web interface under Hardware -> Temperatures
3. Use SNMP tools to query temperature sensor names

Temperature Rise Sensor Purpose:
- Measures thermal efficiency (outlet temp - inlet temp)
- Useful for rack cooling analysis
- Not essential for basic system monitoring
- Individual temperature sensors provide the core monitoring

If you don't have inlet/outlet sensors, this is normal and expected for many
Dell server models. The integration will still provide all other temperature
monitoring capabilities.
""")