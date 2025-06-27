"""Config flow for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
)
from pysnmp.proto import rfc1902

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_AUTH_PROTOCOL,
    CONF_AUTH_PASSWORD,
    CONF_PRIV_PROTOCOL,
    CONF_PRIV_PASSWORD,
    CONF_PORT,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    CONF_CONNECTION_TYPE,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_DETAILED_MEMORY,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    CONF_DISCOVERED_POWER_CONSUMPTION,
    CONNECTION_TYPES,
    DEFAULT_PORT,
    DEFAULT_SNMP_PORT,
    DEFAULT_COMMUNITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    DEFAULT_CONNECTION_TYPE,
    SNMP_VERSIONS,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    SNMP_WALK_OIDS,
    DOMAIN,
)
from .redfish_client import RedfishClient, RedfishError

_LOGGER = logging.getLogger(__name__)


def _create_auth_data(data: dict[str, Any]) -> CommunityData | UsmUserData:
    """Create the appropriate authentication data for SNMP."""
    snmp_version = data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
    
    if snmp_version == "v3":
        username = data.get(CONF_USERNAME, "")
        auth_protocol = data.get(CONF_AUTH_PROTOCOL, "none")
        auth_password = data.get(CONF_AUTH_PASSWORD, "")
        priv_protocol = data.get(CONF_PRIV_PROTOCOL, "none")
        priv_password = data.get(CONF_PRIV_PASSWORD, "")
        
        # Map protocol names to pysnmp protocol objects
        auth_proto = None
        if auth_protocol != "none":
            auth_proto = getattr(rfc1902, SNMP_AUTH_PROTOCOLS[auth_protocol], None)
        
        priv_proto = None
        if priv_protocol != "none":
            priv_proto = getattr(rfc1902, SNMP_PRIV_PROTOCOLS[priv_protocol], None)
        
        return UsmUserData(
            userName=username,
            authKey=auth_password if auth_proto else None,
            privKey=priv_password if priv_proto else None,
            authProtocol=auth_proto,
            privProtocol=priv_proto,
        )
    else:
        # SNMP v2c
        community = data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
        return CommunityData(community)


def _get_dynamic_schema(connection_type: str = DEFAULT_CONNECTION_TYPE) -> vol.Schema:
    """Get schema based on connection type."""
    base_schema = {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_CONNECTION_TYPE, default=DEFAULT_CONNECTION_TYPE): vol.In(CONNECTION_TYPES),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
    }
    
    if connection_type == "redfish":
        base_schema.update({
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_USERNAME, default="root"): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        })
    else:  # SNMP
        base_schema.update({
            vol.Optional(CONF_PORT, default=DEFAULT_SNMP_PORT): int,
            vol.Optional(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): vol.In(SNMP_VERSIONS),
            vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
            vol.Optional(CONF_USERNAME): str,
            vol.Optional(CONF_AUTH_PROTOCOL, default="none"): vol.In(list(SNMP_AUTH_PROTOCOLS.keys())),
            vol.Optional(CONF_AUTH_PASSWORD): str,
            vol.Optional(CONF_PRIV_PROTOCOL, default="none"): vol.In(list(SNMP_PRIV_PROTOCOLS.keys())),
            vol.Optional(CONF_PRIV_PASSWORD): str,
        })
    
    return vol.Schema(base_schema)


STEP_USER_DATA_SCHEMA = _get_dynamic_schema()


async def validate_redfish_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Redfish connection."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    verify_ssl = data[CONF_VERIFY_SSL]

    client = RedfishClient(hass, host, username, password, port, verify_ssl)

    try:
        # Test connection to iDRAC
        _LOGGER.debug("Testing Redfish connection to %s:%s", host, port)
        if not await client.test_connection():
            _LOGGER.error("Redfish connection test failed to %s:%s", host, port)
            raise CannotConnect

        # Get service root to verify API access
        _LOGGER.debug("Getting service root from %s:%s", host, port)
        service_root = await client.get_service_root()
        if not service_root:
            _LOGGER.error("Failed to get service root from %s:%s", host, port)
            raise CannotConnect

        # Get system info for device identification
        _LOGGER.debug("Getting system info from %s:%s", host, port)
        system_info = await client.get_system_info()
        device_name = "Dell iDRAC"
        if system_info:
            model = system_info.get("Model")
            if model:
                device_name = f"Dell {model}"

        _LOGGER.info("Successfully validated Redfish connection to %s:%s", host, port)
        return {"title": f"{device_name} ({host})", "service_info": service_root}

    except RedfishError as exc:
        _LOGGER.error("Redfish authentication error for %s:%s: %s", host, port, exc)
        raise InvalidAuth
    except Exception as exc:
        _LOGGER.exception("Unexpected exception during Redfish validation for %s:%s: %s", host, port, exc)
        raise CannotConnect
    finally:
        await client.close()


async def validate_snmp_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate SNMP connection and discover sensors."""
    _LOGGER.info("Starting iDRAC SNMP validation for host: %s", data.get(CONF_HOST))
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    snmp_version = data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)

    try:
        _LOGGER.info("Creating SNMP engine and connection objects")
        engine = SnmpEngine()
        auth_data = _create_auth_data(data)
        transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
        context_data = ContextData()

        test_oid = ObjectType(ObjectIdentity("1.3.6.1.4.1.674.10892.5.4.600.30.1.6.1.3"))

        _LOGGER.info("Testing SNMP connection to %s:%s with version %s", host, port, snmp_version)
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            auth_data,
            transport_target,
            context_data,
            test_oid,
        )

        if error_indication:
            _LOGGER.error("SNMP error indication: %s", error_indication)
            raise CannotConnect
        elif error_status:
            _LOGGER.error("SNMP error status: %s at %s", error_status.prettyPrint(), error_index and var_binds[int(error_index) - 1][0] or '?')
            raise InvalidAuth

        _LOGGER.info("Successfully connected to iDRAC via SNMP, discovering sensors...")

        discovered_fans = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["fans"])
        discovered_cpus = await _discover_cpu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["cpu_temps"])
        discovered_psus = await _discover_psu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_status"])
        discovered_voltage_probes = await _discover_voltage_probes(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_voltage"])
        
        # Try multiple memory health OID bases
        discovered_memory = []
        memory_oid_bases = [
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1",  # Primary memory health OID base
            "1.3.6.1.4.1.674.10892.5.4.1100.40.1.8.1",  # Secondary memory health OID base
            "1.3.6.1.4.1.674.10892.5.4.1100.30.1.8.1",  # Alternative memory health OID base
        ]
        
        for oid_base in memory_oid_bases:
            _LOGGER.debug("Trying memory discovery with OID base: %s", oid_base)
            memory_results = await _discover_memory_sensors(engine, auth_data, transport_target, context_data, oid_base)
            if memory_results:
                discovered_memory.extend(memory_results)
                _LOGGER.info("Found %d memory modules with OID base %s", len(memory_results), oid_base)
                break

        # Remove duplicates and sort
        discovered_memory = sorted(list(set(discovered_memory)))
        
        # Discover storage components
        discovered_virtual_disks = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["virtual_disks"])
        discovered_physical_disks = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["physical_disks"])
        discovered_storage_controllers = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["storage_controllers"])
        
        # Discover new sensor types
        discovered_detailed_memory = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["detailed_memory"])
        discovered_system_voltages = await _discover_system_voltages(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["system_voltages"])
        discovered_power_consumption = await _discover_power_consumption_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["power_consumption"])

        _LOGGER.info("Discovered %d fans, %d CPU temperature sensors, %d PSU sensors, %d voltage probes, %d memory modules, %d virtual disks, %d physical disks, %d storage controllers, %d detailed memory modules, %d system voltages, %d power consumption sensors", 
                     len(discovered_fans), len(discovered_cpus), len(discovered_psus), len(discovered_voltage_probes), len(discovered_memory),
                     len(discovered_virtual_disks), len(discovered_physical_disks), len(discovered_storage_controllers), len(discovered_detailed_memory),
                     len(discovered_system_voltages), len(discovered_power_consumption))

        # Store discovered sensors in data for later use
        data[CONF_DISCOVERED_FANS] = discovered_fans
        data[CONF_DISCOVERED_CPUS] = discovered_cpus
        data[CONF_DISCOVERED_PSUS] = discovered_psus
        data[CONF_DISCOVERED_VOLTAGE_PROBES] = discovered_voltage_probes
        data[CONF_DISCOVERED_MEMORY] = discovered_memory
        data[CONF_DISCOVERED_VIRTUAL_DISKS] = discovered_virtual_disks
        data[CONF_DISCOVERED_PHYSICAL_DISKS] = discovered_physical_disks
        data[CONF_DISCOVERED_STORAGE_CONTROLLERS] = discovered_storage_controllers
        data[CONF_DISCOVERED_DETAILED_MEMORY] = discovered_detailed_memory
        data[CONF_DISCOVERED_SYSTEM_VOLTAGES] = discovered_system_voltages
        data[CONF_DISCOVERED_POWER_CONSUMPTION] = discovered_power_consumption

        # Get system info
        device_name = "Dell iDRAC"
        _LOGGER.info("Successfully validated SNMP connection to %s:%s", host, port)
        return {"title": f"{device_name} ({host})"}

    except Exception as exc:
        _LOGGER.exception("Error validating SNMP connection to %s:%s: %s", host, port, exc)
        if "authentication" in str(exc).lower() or "authorization" in str(exc).lower():
            raise InvalidAuth
        raise CannotConnect


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    
    if connection_type == "redfish":
        return await validate_redfish_input(hass, data)
    else:
        return await validate_snmp_input(hass, data)


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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dell iDRAC."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_type = DEFAULT_CONNECTION_TYPE

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Update connection type and schema if changed
            if CONF_CONNECTION_TYPE in user_input:
                new_connection_type = user_input[CONF_CONNECTION_TYPE]
                if new_connection_type != self._connection_type:
                    self._connection_type = new_connection_type
                    # Show form again with updated schema
                    return self.async_show_form(
                        step_id="user", 
                        data_schema=_get_dynamic_schema(self._connection_type),
                        errors=errors
                    )
            
            # Set unique ID based on host and connection type
            unique_id = f"{user_input[CONF_HOST]}_{user_input.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", 
            data_schema=_get_dynamic_schema(self._connection_type), 
            errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""