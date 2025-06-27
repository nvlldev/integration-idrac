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
    CONF_SNMP_PORT,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
    CONF_CONNECTION_TYPE,
    CONF_REQUEST_TIMEOUT,
    CONF_SESSION_TIMEOUT,
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
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SESSION_TIMEOUT,
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


# Step 1: Connection method selection
STEP_CONNECTION_TYPE_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_CONNECTION_TYPE, default=DEFAULT_CONNECTION_TYPE): vol.In(CONNECTION_TYPES),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=300)
    ),
})

# Step 2a: Redfish configuration
STEP_REDFISH_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Required(CONF_USERNAME, default="root"): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    vol.Optional(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=120)
    ),
    vol.Optional(CONF_SESSION_TIMEOUT, default=DEFAULT_SESSION_TIMEOUT): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=180)
    ),
})

# Step 2b: SNMP configuration  
STEP_SNMP_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT, default=DEFAULT_SNMP_PORT): int,
    vol.Optional(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): vol.In(SNMP_VERSIONS),
    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
    vol.Optional(CONF_USERNAME): str,
    vol.Optional(CONF_AUTH_PROTOCOL, default="none"): vol.In(list(SNMP_AUTH_PROTOCOLS.keys())),
    vol.Optional(CONF_AUTH_PASSWORD): str,
    vol.Optional(CONF_PRIV_PROTOCOL, default="none"): vol.In(list(SNMP_PRIV_PROTOCOLS.keys())),
    vol.Optional(CONF_PRIV_PASSWORD): str,
})

# Step 2c: Hybrid Redfish configuration
STEP_HYBRID_REDFISH_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    vol.Required(CONF_USERNAME, default="root"): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    vol.Optional(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=120)
    ),
    vol.Optional(CONF_SESSION_TIMEOUT, default=DEFAULT_SESSION_TIMEOUT): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=180)
    ),
})

# Step 3: Hybrid SNMP configuration
STEP_HYBRID_SNMP_SCHEMA = vol.Schema({
    vol.Optional(CONF_SNMP_PORT, default=DEFAULT_SNMP_PORT): int,
    vol.Optional(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): vol.In(SNMP_VERSIONS),
    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
    vol.Optional(CONF_AUTH_PROTOCOL, default="none"): vol.In(list(SNMP_AUTH_PROTOCOLS.keys())),
    vol.Optional(CONF_AUTH_PASSWORD): str,
    vol.Optional(CONF_PRIV_PROTOCOL, default="none"): vol.In(list(SNMP_PRIV_PROTOCOLS.keys())),
    vol.Optional(CONF_PRIV_PASSWORD): str,
})


async def validate_redfish_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Redfish connection."""
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    verify_ssl = data[CONF_VERIFY_SSL]
    request_timeout = data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
    session_timeout = data.get(CONF_SESSION_TIMEOUT, DEFAULT_SESSION_TIMEOUT)

    client = RedfishClient(hass, host, username, password, port, verify_ssl, request_timeout, session_timeout)

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


async def validate_hybrid_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate hybrid connection (SNMP for data, Redfish for controls)."""
    host = data[CONF_HOST]
    
    # Validate Redfish connection for controls
    redfish_port = data.get(CONF_PORT, DEFAULT_PORT)
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    verify_ssl = data.get(CONF_VERIFY_SSL, False)
    request_timeout = data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
    session_timeout = data.get(CONF_SESSION_TIMEOUT, DEFAULT_SESSION_TIMEOUT)

    redfish_client = RedfishClient(hass, host, username, password, redfish_port, verify_ssl, request_timeout, session_timeout)

    try:
        # Test Redfish connection
        _LOGGER.debug("Testing Redfish connection for hybrid mode to %s:%s", host, redfish_port)
        if not await redfish_client.test_connection():
            raise CannotConnect("Failed to connect to Redfish API")

        redfish_info = await redfish_client.get_service_root()
        if not redfish_info:
            raise CannotConnect("Failed to get Redfish service root")

    finally:
        await redfish_client.close()

    # Validate SNMP connection for data collection
    snmp_port = data.get(CONF_SNMP_PORT, DEFAULT_SNMP_PORT)
    snmp_version = data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)
    
    # Create SNMP auth data for testing
    snmp_auth_data = _create_auth_data(data)
    
    # Test SNMP connection
    engine = SnmpEngine()
    transport_target = UdpTransportTarget((host, snmp_port), timeout=5, retries=1)
    context_data = ContextData()

    try:
        _LOGGER.debug("Testing SNMP connection for hybrid mode to %s:%s", host, snmp_port)
        
        # Try to get system uptime as a basic connectivity test
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            snmp_auth_data,
            transport_target,
            context_data,
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),  # sysUpTime
        )

        if error_indication:
            raise CannotConnect(f"SNMP connection failed: {error_indication}")
        elif error_status:
            raise CannotConnect(f"SNMP error: {error_status.prettyPrint()}")

        _LOGGER.debug("SNMP test successful for hybrid mode")

    except Exception as exc:
        _LOGGER.error("SNMP test failed for hybrid mode: %s", exc)
        raise CannotConnect(f"SNMP connection failed: {exc}") from exc
    finally:
        engine.close()

    # Get device name from Redfish for title  
    device_name = "Dell iDRAC"
    system_info = await redfish_client.get_system_info()
    if system_info:
        model = system_info.get("Model")
        if model:
            device_name = f"Dell {model}"

    _LOGGER.info("Successfully validated hybrid connection to %s", host)
    return {
        "title": f"{device_name} ({host}) - Hybrid Mode",
        "redfish_info": redfish_info,
        "snmp_version": snmp_version,
    }


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    connection_type = data.get(CONF_CONNECTION_TYPE, DEFAULT_CONNECTION_TYPE)
    
    if connection_type == "redfish":
        return await validate_redfish_input(hass, data)
    elif connection_type == "hybrid":
        return await validate_hybrid_input(hass, data)
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
        self._config_data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - connection type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store basic configuration
            self._config_data.update(user_input)
            
            # Set unique ID based on host and connection type
            unique_id = f"{user_input[CONF_HOST]}_{user_input[CONF_CONNECTION_TYPE]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            connection_type = user_input[CONF_CONNECTION_TYPE]
            
            # Route to appropriate next step based on connection type
            if connection_type == "redfish":
                return await self.async_step_redfish()
            elif connection_type == "snmp":
                return await self.async_step_snmp()
            elif connection_type == "hybrid":
                return await self.async_step_hybrid_redfish()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CONNECTION_TYPE_SCHEMA,
            errors=errors,
            description_placeholders={
                "redfish_desc": "Fast setup, full control features, moderate performance",
                "snmp_desc": "Fast performance, basic monitoring only",
                "hybrid_desc": "Best of both: SNMP speed + Redfish controls"
            }
        )

    async def async_step_redfish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Redfish configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine all configuration data
            self._config_data.update(user_input)
            
            try:
                info = await validate_redfish_input(self.hass, self._config_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=self._config_data)

        return self.async_show_form(
            step_id="redfish",
            data_schema=STEP_REDFISH_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._config_data.get(CONF_HOST, ""),
            }
        )

    async def async_step_snmp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMP configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine all configuration data
            self._config_data.update(user_input)
            
            try:
                info = await validate_snmp_input(self.hass, self._config_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=self._config_data)

        return self.async_show_form(
            step_id="snmp",
            data_schema=STEP_SNMP_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._config_data.get(CONF_HOST, ""),
            }
        )

    async def async_step_hybrid_redfish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode Redfish configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store Redfish configuration
            self._config_data.update(user_input)
            
            # Validate Redfish connection
            try:
                # Test Redfish connection before proceeding to SNMP step
                redfish_data = dict(self._config_data)
                await validate_redfish_input(self.hass, redfish_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Redfish connection successful, proceed to SNMP configuration
                return await self.async_step_hybrid_snmp()

        return self.async_show_form(
            step_id="hybrid_redfish",
            data_schema=STEP_HYBRID_REDFISH_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._config_data.get(CONF_HOST, ""),
                "step": "Redfish Control Settings",
                "purpose": "Used for LED control and system resets"
            }
        )

    async def async_step_hybrid_snmp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode SNMP configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine all configuration data
            self._config_data.update(user_input)
            
            try:
                info = await validate_hybrid_input(self.hass, self._config_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=self._config_data)

        return self.async_show_form(
            step_id="hybrid_snmp",
            data_schema=STEP_HYBRID_SNMP_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": self._config_data.get(CONF_HOST, ""),
                "step": "SNMP Data Collection Settings",
                "purpose": "Used for fast sensor data monitoring"
            }
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""