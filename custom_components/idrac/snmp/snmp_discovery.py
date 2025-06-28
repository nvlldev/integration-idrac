"""SNMP sensor discovery functions for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
)

_LOGGER = logging.getLogger(__name__)


async def discover_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover sensors by testing sequential indices."""
    _LOGGER.debug("Starting sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 20 (most systems won't have more than 20 of any given sensor type)
    for index in range(1, 21):
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
                # Check if we got a valid response with meaningful data
                for name, val in var_binds:
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        val_str = str(val).strip()
                        # Only include sensors that have non-empty, meaningful values
                        if val_str and val_str not in ["", "None", "0", "null"]:
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found sensor at index %d: %s = %s", index, name, val)
                        else:
                            _LOGGER.debug("Skipping sensor at index %d with empty/invalid value: %s = %s", index, name, val)
                        break
            else:
                # Log debug info for failed attempts
                if error_indication:
                    _LOGGER.debug("Sensor discovery failed at index %d: %s", index, error_indication)
                elif error_status:
                    _LOGGER.debug("Sensor discovery failed at index %d: %s", index, error_status.prettyPrint())
                    
        except Exception as exc:
            _LOGGER.debug("Exception during sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_cpu_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover CPU temperature sensors, filtering out inlet/outlet temps."""
    _LOGGER.debug("Starting CPU sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 20 
    for index in range(1, 21):
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
                        val_str = str(val).strip()
                        # Only include CPU sensors (skip Inlet/Exhaust temps) and ensure they have names
                        if val_str and "CPU" in val_str and "Temp" in val_str:
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found CPU sensor at index %d: %s = %s", index, name, val)
                        elif val_str:
                            _LOGGER.debug("Skipping non-CPU sensor at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during CPU sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered CPU sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_fan_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover fan sensors."""
    _LOGGER.debug("Starting fan sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 20
    for index in range(1, 21):
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
                        val_str = str(val).strip()
                        # Only include fans that have meaningful names (System Board Fan, etc.)
                        if val_str and ("Fan" in val_str or "Cooling" in val_str):
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found fan sensor at index %d: %s = %s", index, name, val)
                        elif val_str:
                            _LOGGER.debug("Skipping non-fan sensor at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during fan sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered fan sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_psu_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover PSU sensors by testing specific PSU-related indices."""
    _LOGGER.debug("Starting PSU sensor discovery for base OID: %s", base_oid)
    discovered_psus = []
    
    # Test indices from 1 to 10 (most systems won't have more than 10 PSUs)
    for index in range(1, 11):
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
                # Check if we got a valid response
                for name, val in var_binds:
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        # For PSUs, we want to check if the value indicates a real PSU
                        val_str = str(val)
                        if val_str and val_str.strip() and val_str not in ["", "None", "0"]:
                            discovered_psus.append(index)
                            _LOGGER.debug("Found PSU at index %d: %s = %s", index, name, val)
                            break
            else:
                if error_indication:
                    _LOGGER.debug("PSU discovery failed at index %d: %s", index, error_indication)
                elif error_status:
                    _LOGGER.debug("PSU discovery failed at index %d: %s", index, error_status.prettyPrint())
                    
        except Exception as exc:
            _LOGGER.debug("Exception during PSU discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered PSUs for base OID %s: %s", base_oid, discovered_psus)
    return discovered_psus


async def discover_voltage_probes(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover voltage probe sensors."""
    _LOGGER.debug("Starting voltage probe discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 20
    for index in range(1, 21):
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
                        val_str = str(val).strip()
                        # Only include voltage probes that have meaningful names (PS, CPU, etc.)
                        if val_str and any(keyword in val_str for keyword in ["PS", "CPU", "System", "Board", "PG"]):
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found voltage probe at index %d: %s = %s", index, name, val)
                        elif val_str:
                            _LOGGER.debug("Skipping voltage probe at index %d with generic name: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during voltage probe discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered voltage probes for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_memory_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover memory sensors."""
    _LOGGER.debug("Starting memory sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 20
    for index in range(1, 21):
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
                        val_str = str(val).strip()
                        # Only include memory slots that have meaningful names (DIMM.Socket.XX format)
                        if val_str and ("DIMM" in val_str or "Socket" in val_str):
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found memory sensor at index %d: %s = %s", index, name, val)
                        elif val_str:
                            _LOGGER.debug("Skipping non-memory sensor at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during memory sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered memory sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_system_voltages(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover system voltage sensors."""
    return await discover_sensors(engine, auth_data, transport_target, context_data, base_oid)


async def discover_power_consumption_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover power consumption sensors."""
    _LOGGER.debug("Starting power consumption sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 10 (power consumption typically has fewer sensors)
    for index in range(1, 11):
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
                        # For power consumption, we look for actual numeric values or descriptive names
                        try:
                            # Check if it's a numeric value (power reading)
                            int(val)
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found power consumption sensor at index %d: %s = %s", index, name, val)
                        except (ValueError, TypeError):
                            # Check if it's a descriptive name containing power-related keywords
                            val_str = str(val).strip()
                            if val_str and any(keyword in val_str for keyword in ["Power", "Current", "Consumption", "PS"]):
                                discovered_sensors.append(index)
                                _LOGGER.debug("Found power consumption sensor at index %d: %s = %s", index, name, val)
                            elif val_str:
                                _LOGGER.debug("Skipping non-power sensor at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during power consumption sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered power consumption sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_intrusion_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover chassis intrusion sensors."""
    _LOGGER.debug("Starting intrusion sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 5 (intrusion sensors are typically few)
    for index in range(1, 6):
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
                        val_str = str(val).strip()
                        # Any non-empty string indicates a valid intrusion sensor location
                        # The actual intrusion detection will be determined by reading the status
                        if val_str:
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found intrusion sensor at index %d: %s = %s", index, name, val)
                        else:
                            _LOGGER.debug("Skipping empty intrusion sensor at index %d", index)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during intrusion sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered intrusion sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_battery_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover system battery sensors."""
    _LOGGER.debug("Starting battery sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 5 (battery sensors are typically few)
    for index in range(1, 6):
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
                        # For battery, we expect numeric readings
                        try:
                            int(val)
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found battery sensor at index %d: %s = %s", index, name, val)
                        except (ValueError, TypeError):
                            _LOGGER.debug("Skipping non-numeric battery reading at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during battery sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered battery sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors


async def discover_processor_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover processor sensors."""
    _LOGGER.debug("Starting processor sensor discovery for base OID: %s", base_oid)
    discovered_sensors = []
    
    # Test indices from 1 to 10 (processor sensors)
    for index in range(1, 11):
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
                        val_str = str(val).strip()
                        # Look for processor-related keywords
                        if val_str and any(keyword in val_str for keyword in ["CPU", "Processor", "PCI"]):
                            discovered_sensors.append(index)
                            _LOGGER.debug("Found processor sensor at index %d: %s = %s", index, name, val)
                        elif val_str:
                            _LOGGER.debug("Skipping non-processor sensor at index %d: %s = %s", index, name, val)
                        break
                        
        except Exception as exc:
            _LOGGER.debug("Exception during processor sensor discovery at index %d: %s", index, exc)
            continue
    
    _LOGGER.debug("Discovered processor sensors for base OID %s: %s", base_oid, discovered_sensors)
    return discovered_sensors