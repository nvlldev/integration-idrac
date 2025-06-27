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


async def _discover_sensors(
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
                # Check if we got a valid response (not just "no such object")
                for name, val in var_binds:
                    if val is not None and str(val) != "No Such Object currently exists at this OID":
                        discovered_sensors.append(index)
                        _LOGGER.debug("Found sensor at index %d: %s = %s", index, name, val)
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


async def _discover_cpu_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover CPU temperature sensors, filtering out inlet/outlet temps."""
    all_temp_sensors = await _discover_sensors(
        engine, auth_data, transport_target, context_data, base_oid
    )
    
    return [sensor_id for sensor_id in all_temp_sensors if sensor_id > 2]


async def _discover_psu_sensors(
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


async def _discover_voltage_probes(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover voltage probe sensors."""
    return await _discover_sensors(engine, auth_data, transport_target, context_data, base_oid)


async def _discover_memory_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover memory sensors."""
    return await _discover_sensors(engine, auth_data, transport_target, context_data, base_oid)


async def _discover_system_voltages(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover system voltage sensors."""
    return await _discover_sensors(engine, auth_data, transport_target, context_data, base_oid)


async def _discover_power_consumption_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover power consumption sensors."""
    return await _discover_sensors(engine, auth_data, transport_target, context_data, base_oid)