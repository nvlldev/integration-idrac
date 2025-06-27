"""Config flow for Dell iDRAC integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.helpers import selector
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
    CONF_DISCOVERED_INTRUSION,
    CONF_DISCOVERED_BATTERY,
    CONF_DISCOVERED_PROCESSORS,
    CONNECTION_TYPES,
    DEFAULT_PORT,
    DEFAULT_SNMP_PORT,
    DEFAULT_COMMUNITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_SESSION_TIMEOUT,
    SNMP_VERSIONS,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    SNMP_WALK_OIDS,
    DOMAIN,
)
from .redfish.redfish_client import RedfishClient, RedfishError

_LOGGER = logging.getLogger(__name__)


# Step 1: Host and connection type selection
STEP_HOST_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
    vol.Required(CONF_CONNECTION_TYPE, default="redfish"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=CONNECTION_TYPES,
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=10,
            max=300,
            step=5,
            unit_of_measurement="seconds",
            mode=selector.NumberSelectorMode.BOX
        )
    ),
})

# Step 2a: Redfish credentials
STEP_REDFISH_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=65535,
            mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Required(CONF_USERNAME, default="root"): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_VERIFY_SSL, default=False): selector.BooleanSelector(),
    vol.Optional(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=10,
            max=300,
            step=10,
            unit_of_measurement="seconds",
            mode=selector.NumberSelectorMode.SLIDER
        )
    ),
    vol.Optional(CONF_SESSION_TIMEOUT, default=DEFAULT_SESSION_TIMEOUT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=30,
            max=600,
            step=15,
            unit_of_measurement="seconds",
            mode=selector.NumberSelectorMode.SLIDER
        )
    ),
})

# Step 2b: SNMP version selection
STEP_SNMP_VERSION_SCHEMA = vol.Schema({
    vol.Optional(CONF_SNMP_PORT, default=DEFAULT_SNMP_PORT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=65535,
            mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Required(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SNMP_VERSIONS,
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
})

# Step 3a: SNMP v2c credentials (community string)
STEP_SNMP_V2C_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
})

# Step 3b: SNMP v3 credentials (username/password)
STEP_SNMP_V3_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
    vol.Optional(CONF_AUTH_PROTOCOL, default="sha"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(SNMP_AUTH_PROTOCOLS.keys()),
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional(CONF_AUTH_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_PRIV_PROTOCOL, default="aes128"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(SNMP_PRIV_PROTOCOLS.keys()),
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional(CONF_PRIV_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
})

# Step 3: Hybrid Redfish credentials
STEP_HYBRID_REDFISH_SCHEMA = vol.Schema({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=65535,
            mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Required(CONF_USERNAME, default="root"): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
    vol.Required(CONF_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_VERIFY_SSL, default=False): selector.BooleanSelector(),
    vol.Optional(CONF_REQUEST_TIMEOUT, default=DEFAULT_REQUEST_TIMEOUT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=10,
            max=300,
            step=10,
            unit_of_measurement="seconds",
            mode=selector.NumberSelectorMode.SLIDER
        )
    ),
    vol.Optional(CONF_SESSION_TIMEOUT, default=DEFAULT_SESSION_TIMEOUT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=30,
            max=600,
            step=15,
            unit_of_measurement="seconds",
            mode=selector.NumberSelectorMode.SLIDER
        )
    ),
})

# Step 4: Hybrid SNMP version selection
STEP_HYBRID_SNMP_VERSION_SCHEMA = vol.Schema({
    vol.Optional(CONF_SNMP_PORT, default=DEFAULT_SNMP_PORT): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=65535,
            mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Required(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=SNMP_VERSIONS,
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
})

# Step 5a: Hybrid SNMP v2c credentials
STEP_HYBRID_SNMP_V2C_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
})

# Step 5b: Hybrid SNMP v3 credentials
STEP_HYBRID_SNMP_V3_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    ),
    vol.Optional(CONF_AUTH_PROTOCOL, default="sha"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(SNMP_AUTH_PROTOCOLS.keys()),
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional(CONF_AUTH_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_PRIV_PROTOCOL, default="aes128"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(SNMP_PRIV_PROTOCOLS.keys()),
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional(CONF_PRIV_PASSWORD): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    ),
})


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


async def validate_redfish_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Redfish connection."""
    host = data[CONF_HOST]
    port = int(data[CONF_PORT])  # Ensure port is an integer
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    verify_ssl = data[CONF_VERIFY_SSL]
    request_timeout = int(data.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))
    session_timeout = int(data.get(CONF_SESSION_TIMEOUT, DEFAULT_SESSION_TIMEOUT))

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
        _LOGGER.error("Unexpected exception during Redfish validation for %s:%s: %s", host, port, exc)
        raise CannotConnect
    finally:
        await client.close()


async def validate_snmp_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate SNMP connection and discover sensors."""
    _LOGGER.info("Starting iDRAC SNMP validation for host: %s", data.get(CONF_HOST))
    host = data[CONF_HOST]
    port = int(data[CONF_SNMP_PORT])  # Ensure port is an integer
    snmp_version = data.get(CONF_SNMP_VERSION, DEFAULT_SNMP_VERSION)

    try:
        _LOGGER.info("Creating SNMP engine and connection objects")
        
        # Use executor to avoid blocking I/O operations during SNMP initialization
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _init_snmp():
            engine = SnmpEngine()
            auth_data = _create_auth_data(data)
            transport_target = UdpTransportTarget((host, port), timeout=10, retries=2)
            context_data = ContextData()
            return engine, auth_data, transport_target, context_data
        
        engine, auth_data, transport_target, context_data = await loop.run_in_executor(None, _init_snmp)

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

        # Import discovery functions
        from .discovery import (
            _discover_sensors,
            _discover_cpu_sensors,
            _discover_fan_sensors,
            _discover_psu_sensors,
            _discover_voltage_probes,
            _discover_memory_sensors,
            _discover_system_voltages,
            _discover_power_consumption_sensors,
            _discover_intrusion_sensors,
            _discover_battery_sensors,
            _discover_processor_sensors,
        )
        
        discovered_fans = await _discover_fan_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["fans"])
        discovered_cpus = await _discover_cpu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["cpu_temps"])
        discovered_psus = await _discover_psu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_status"])
        discovered_voltage_probes = await _discover_voltage_probes(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_voltage"])
        
        # Try multiple memory health OID bases
        discovered_memory = []
        memory_oid_bases = [
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8.1",
            "1.3.6.1.4.1.674.10892.5.4.1100.40.1.8.1",
            "1.3.6.1.4.1.674.10892.5.4.1100.30.1.8.1",
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
        
        # Discover newly added sensor types
        discovered_intrusion = await _discover_intrusion_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["intrusion_detection"])
        discovered_battery = await _discover_battery_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["system_battery"])
        discovered_processors = await _discover_processor_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["processors"])

        _LOGGER.info("Discovered %d fans, %d CPU temperature sensors, %d PSU sensors, %d voltage probes, %d memory modules, %d virtual disks, %d physical disks, %d storage controllers, %d detailed memory modules, %d system voltages, %d power consumption sensors, %d intrusion sensors, %d battery sensors, %d processor sensors", 
                     len(discovered_fans), len(discovered_cpus), len(discovered_psus), len(discovered_voltage_probes), len(discovered_memory),
                     len(discovered_virtual_disks), len(discovered_physical_disks), len(discovered_storage_controllers), len(discovered_detailed_memory),
                     len(discovered_system_voltages), len(discovered_power_consumption), len(discovered_intrusion), len(discovered_battery), len(discovered_processors))

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
        data[CONF_DISCOVERED_INTRUSION] = discovered_intrusion
        data[CONF_DISCOVERED_BATTERY] = discovered_battery
        data[CONF_DISCOVERED_PROCESSORS] = discovered_processors

        return {"title": f"Dell iDRAC ({host})"}

    except InvalidAuth:
        raise
    except CannotConnect:
        raise
    except Exception as exc:
        _LOGGER.error("Unexpected exception during SNMP validation for %s:%s: %s", host, port, exc)
        raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dell iDRAC."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - host and connection type selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store the initial data
            self.data.update(user_input)
            
            # Check for existing entries with the same host
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            connection_type = user_input[CONF_CONNECTION_TYPE]
            
            # Route to appropriate next step based on connection type
            if connection_type == "redfish":
                return await self.async_step_redfish()
            elif connection_type == "snmp":
                return await self.async_step_snmp_version()
            elif connection_type == "hybrid":
                return await self.async_step_hybrid_redfish()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_HOST_SCHEMA,
            errors=errors,
            description_placeholders={
                "connection_types": ", ".join(CONNECTION_TYPES)
            }
        )

    async def async_step_redfish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Redfish credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                info = await validate_redfish_input(self.hass, self.data)
                return self.async_create_entry(title=info["title"], data=self.data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="redfish",
            data_schema=STEP_REDFISH_SCHEMA,
            errors=errors,
        )

    async def async_step_snmp_version(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMP version selection step."""
        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            snmp_version = user_input[CONF_SNMP_VERSION]
            
            # Route to appropriate credentials step based on SNMP version
            if snmp_version == "v2c":
                return await self.async_step_snmp_v2c()
            elif snmp_version == "v3":
                return await self.async_step_snmp_v3()

        return self.async_show_form(
            step_id="snmp_version",
            data_schema=STEP_SNMP_VERSION_SCHEMA,
        )

    async def async_step_snmp_v2c(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMP v2c credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                info = await validate_snmp_input(self.hass, self.data)
                return self.async_create_entry(title=info["title"], data=self.data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="snmp_v2c",
            data_schema=STEP_SNMP_V2C_SCHEMA,
            errors=errors,
        )

    async def async_step_snmp_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SNMP v3 credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                info = await validate_snmp_input(self.hass, self.data)
                return self.async_create_entry(title=info["title"], data=self.data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="snmp_v3",
            data_schema=STEP_SNMP_V3_SCHEMA,
            errors=errors,
        )

    async def async_step_hybrid_redfish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode Redfish credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                # Validate Redfish connection first
                await validate_redfish_input(self.hass, self.data)
                # Continue to SNMP configuration
                return await self.async_step_hybrid_snmp_version()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hybrid_redfish",
            data_schema=STEP_HYBRID_REDFISH_SCHEMA,
            errors=errors,
        )

    async def async_step_hybrid_snmp_version(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode SNMP version selection step."""
        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            snmp_version = user_input[CONF_SNMP_VERSION]
            
            # Route to appropriate credentials step based on SNMP version
            if snmp_version == "v2c":
                return await self.async_step_hybrid_snmp_v2c()
            elif snmp_version == "v3":
                return await self.async_step_hybrid_snmp_v3()

        return self.async_show_form(
            step_id="hybrid_snmp_version",
            data_schema=STEP_HYBRID_SNMP_VERSION_SCHEMA,
        )

    async def async_step_hybrid_snmp_v2c(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode SNMP v2c credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                info = await validate_snmp_input(self.hass, self.data)
                return self.async_create_entry(title=info["title"], data=self.data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hybrid_snmp_v2c",
            data_schema=STEP_HYBRID_SNMP_V2C_SCHEMA,
            errors=errors,
        )

    async def async_step_hybrid_snmp_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle hybrid mode SNMP v3 credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge with existing data
            self.data.update(user_input)
            
            try:
                info = await validate_snmp_input(self.hass, self.data)
                return self.async_create_entry(title=info["title"], data=self.data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="hybrid_snmp_v3",
            data_schema=STEP_HYBRID_SNMP_V3_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""