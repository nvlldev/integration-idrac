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
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_USERNAME,
    CONF_AUTH_PROTOCOL,
    CONF_AUTH_PASSWORD,
    CONF_PRIV_PROTOCOL,
    CONF_PRIV_PASSWORD,
    CONF_DISCOVERED_CPUS,
    CONF_DISCOVERED_FANS,
    CONF_DISCOVERED_MEMORY,
    CONF_DISCOVERED_PSUS,
    CONF_DISCOVERED_VOLTAGE_PROBES,
    CONF_DISCOVERED_VIRTUAL_DISKS,
    CONF_DISCOVERED_PHYSICAL_DISKS,
    CONF_DISCOVERED_STORAGE_CONTROLLERS,
    CONF_DISCOVERED_DETAILED_MEMORY,
    CONF_DISCOVERED_POWER_CONSUMPTION,
    CONF_DISCOVERED_SYSTEM_VOLTAGES,
    CONF_SCAN_INTERVAL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SNMP_VERSION,
    SNMP_VERSIONS,
    SNMP_AUTH_PROTOCOLS,
    SNMP_PRIV_PROTOCOLS,
    DOMAIN,
    SNMP_WALK_OIDS,
)

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


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SNMP_VERSION, default=DEFAULT_SNMP_VERSION): vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_AUTH_PROTOCOL, default="none"): vol.In(list(SNMP_AUTH_PROTOCOLS.keys())),
        vol.Optional(CONF_AUTH_PASSWORD): str,
        vol.Optional(CONF_PRIV_PROTOCOL, default="none"): vol.In(list(SNMP_PRIV_PROTOCOLS.keys())),
        vol.Optional(CONF_PRIV_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=10, max=300)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect and discover sensors."""
    _LOGGER.info("Starting iDRAC validation for host: %s", data.get(CONF_HOST))
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
            raise CannotConnect(f"SNMP error indication: {error_indication}")
        
        if error_status:
            raise CannotConnect(f"SNMP error status: {error_status}")

        _LOGGER.info("Successfully connected to iDRAC, discovering sensors...")

        discovered_fans = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["fans"])
        discovered_cpus = await _discover_cpu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["cpu_temps"])
        discovered_psus = await _discover_psu_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_status"])
        discovered_voltage_probes = await _discover_voltage_probes(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["psu_voltage"])
        # Try multiple memory health OID bases
        discovered_memory = []
        memory_oid_bases = [
            SNMP_WALK_OIDS["memory_health"],  # Official MIB: 1.3.6.1.4.1.674.10892.5.4.1100.50.1.4 (status)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.5",  # memoryDeviceType (column 5)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.10", # memoryDeviceSize (column 10)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.14", # memoryDeviceSpeed (column 14)
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.23", # memoryDeviceFQDD (column 23)
            # Legacy fallback patterns
            "1.3.6.1.4.1.674.10892.1.1100.50.1.4",    # Legacy memory status
            "1.3.6.1.4.1.674.10892.1.1100.50.1.5",    # Legacy memory health
            "1.3.6.1.4.1.674.10892.1.1100.50.1.6",    # Legacy memory status alt
            # Alternative patterns for different iDRAC versions
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.20", # Memory device status alt
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.7",  # Memory location name
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1.8",  # Memory error status
            "1.3.6.1.4.1.674.10892.5.4.1100.50.1",    # Base memory table
        ]
        
        for oid_base in memory_oid_bases:
            _LOGGER.debug("Trying memory discovery with OID base: %s", oid_base)
            memory_results = await _discover_memory_sensors(engine, auth_data, transport_target, context_data, oid_base)
            if memory_results:
                discovered_memory.extend(memory_results)
                _LOGGER.info("Found %d memory modules with OID base %s", len(memory_results), oid_base)
                break  # Use the first OID base that works
        
        # Remove duplicates and sort
        discovered_memory = sorted(list(set(discovered_memory)))
        
        # Discover storage components
        discovered_virtual_disks = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["virtual_disks"])
        discovered_physical_disks = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["physical_disks"])
        discovered_storage_controllers = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["storage_controllers"])
        
        # Discover new sensor types (enhanced features from comprehensive OID discovery)
        discovered_detailed_memory = await _discover_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["detailed_memory"])
        discovered_system_voltages = await _discover_system_voltages(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["system_voltages"])
        discovered_power_consumption = await _discover_power_consumption_sensors(engine, auth_data, transport_target, context_data, SNMP_WALK_OIDS["power_consumption"])

        _LOGGER.info("Discovered %d fans, %d CPU temperature sensors, %d PSU sensors, %d voltage probes, %d memory modules, %d virtual disks, %d physical disks, %d storage controllers, %d detailed memory modules, %d system voltages, %d power consumption sensors", 
                     len(discovered_fans), len(discovered_cpus), len(discovered_psus), len(discovered_voltage_probes), len(discovered_memory),
                     len(discovered_virtual_disks), len(discovered_physical_disks), len(discovered_storage_controllers),
                     len(discovered_detailed_memory), len(discovered_system_voltages), len(discovered_power_consumption))
        _LOGGER.debug("Fan sensor IDs: %s", discovered_fans)
        _LOGGER.debug("CPU sensor IDs: %s", discovered_cpus)
        _LOGGER.debug("PSU sensor IDs: %s", discovered_psus)
        _LOGGER.debug("Voltage probe IDs: %s", discovered_voltage_probes)
        _LOGGER.debug("Memory module IDs: %s", discovered_memory)
        _LOGGER.debug("Virtual disk IDs: %s", discovered_virtual_disks)
        _LOGGER.debug("Physical disk IDs: %s", discovered_physical_disks)
        _LOGGER.debug("Storage controller IDs: %s", discovered_storage_controllers)
        _LOGGER.debug("Detailed memory module IDs: %s", discovered_detailed_memory)
        _LOGGER.debug("System voltage sensor IDs: %s", discovered_system_voltages)
        _LOGGER.debug("Power consumption sensor IDs: %s", discovered_power_consumption)

        return {
            "title": f"Dell iDRAC ({host})",
            CONF_DISCOVERED_FANS: discovered_fans,
            CONF_DISCOVERED_CPUS: discovered_cpus,
            CONF_DISCOVERED_PSUS: discovered_psus,
            CONF_DISCOVERED_VOLTAGE_PROBES: discovered_voltage_probes,
            CONF_DISCOVERED_MEMORY: discovered_memory,
            CONF_DISCOVERED_VIRTUAL_DISKS: discovered_virtual_disks,
            CONF_DISCOVERED_PHYSICAL_DISKS: discovered_physical_disks,
            CONF_DISCOVERED_STORAGE_CONTROLLERS: discovered_storage_controllers,
            CONF_DISCOVERED_DETAILED_MEMORY: discovered_detailed_memory,
            CONF_DISCOVERED_SYSTEM_VOLTAGES: discovered_system_voltages,
            CONF_DISCOVERED_POWER_CONSUMPTION: discovered_power_consumption,
        }

    except Exception as exc:
        raise CannotConnect(f"Cannot connect to iDRAC: {exc}") from exc


async def _discover_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover available sensors by testing individual OIDs."""
    results = []
    
    try:
        _LOGGER.debug("Testing individual OIDs for base: %s", base_oid)
        
        # Test up to 50 sensor indices to support enterprise configurations (up to 48 DIMMs, 4 CPUs)
        for sensor_id in range(1, 51):
            test_oid = f"{base_oid}.{sensor_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    if (value is not None 
                        and str(value) != "No Such Object currently exists at this OID"
                        and str(value) != "No Such Instance currently exists at this OID"):
                        try:
                            # Try to convert to a numeric value to ensure it's a valid sensor reading
                            numeric_value = float(value)
                            if numeric_value > 0:  # Only include sensors with positive values
                                results.append(sensor_id)
                                _LOGGER.debug("Found sensor ID %d at OID %s with value: %s", sensor_id, test_oid, value)
                            else:
                                _LOGGER.debug("Sensor ID %d at OID %s has invalid value: %s", sensor_id, test_oid, value)
                        except (ValueError, TypeError):
                            _LOGGER.debug("Sensor ID %d at OID %s has non-numeric value: %s", sensor_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("Direct OID testing for %s found %d sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering sensors for OID %s: %s", base_oid, exc)
    
    return results


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
    """Discover PSU sensors by testing status OIDs."""
    results = []
    
    try:
        _LOGGER.debug("Testing PSU status OIDs for base: %s", base_oid)
        
        # Test up to 8 PSU indices (typical server configurations have 1-4 PSUs)
        for psu_id in range(1, 9):
            test_oid = f"{base_oid}.{psu_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    if (value is not None 
                        and str(value) != "No Such Object currently exists at this OID"
                        and str(value) != "No Such Instance currently exists at this OID"):
                        try:
                            # PSU status should be a valid integer (1-6 range typically)
                            status_value = int(value)
                            if 1 <= status_value <= 6:  # Valid Dell iDRAC status range
                                results.append(psu_id)
                                _LOGGER.debug("Found PSU ID %d at OID %s with status: %s", psu_id, test_oid, value)
                            else:
                                _LOGGER.debug("PSU ID %d at OID %s has invalid status: %s", psu_id, test_oid, value)
                        except (ValueError, TypeError):
                            _LOGGER.debug("PSU ID %d at OID %s has non-integer status: %s", psu_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing PSU OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("PSU discovery for %s found %d PSU sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering PSU sensors for OID %s: %s", base_oid, exc)
    
    return results


async def _discover_voltage_probes(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover voltage probe sensors by testing voltage OIDs with focus on PSU voltage ranges."""
    results = []
    
    try:
        _LOGGER.debug("Testing voltage probe OIDs for base: %s", base_oid)
        
        # Test known PSU voltage probe ranges based on test results
        # Found working probes at indices 27, 28 on test system
        test_ranges = [
            range(25, 35),  # Primary PSU voltage range (includes working 27, 28)
            range(20, 25),  # Secondary range for other PSU configurations
            range(35, 45),  # Extended range for systems with more PSUs
            range(1, 20),   # Lower range for other voltage probes (less likely PSU)
        ]
        
        for test_range in test_ranges:
            for probe_id in test_range:
                test_oid = f"{base_oid}.{probe_id}"
                try:
                    error_indication, error_status, error_index, var_binds = await getCmd(
                        engine,
                        auth_data,
                        transport_target,
                        context_data,
                        ObjectType(ObjectIdentity(test_oid)),
                    )
                    
                    if not error_indication and not error_status and var_binds:
                        value = var_binds[0][1]
                        if (value is not None 
                            and str(value) != "No Such Object currently exists at this OID"
                            and str(value) != "No Such Instance currently exists at this OID"
                            and str(value).strip() != ""):  # Handle empty string values
                            try:
                                # Voltage probe reading should be a valid integer (millivolts)
                                voltage_value = int(value)
                                # PSU voltages can range from 3V to 240V (3000-240000 mV)
                                # Expanded range based on test results showing 120V PSUs
                                if 3000 <= voltage_value <= 240000:  # 3V to 240V range for PSU voltages
                                    results.append(probe_id)
                                    voltage_v = voltage_value / 1000.0
                                    _LOGGER.debug("Found PSU voltage probe ID %d at OID %s with value: %s mV (%.3f V)", probe_id, test_oid, voltage_value, voltage_v)
                                elif voltage_value > 0:
                                    # Log other voltage probes for reference but don't include them
                                    voltage_v = voltage_value / 1000.0
                                    _LOGGER.debug("Found other voltage probe ID %d at OID %s with value: %s mV (%.3f V) - outside PSU voltage range", probe_id, test_oid, voltage_value, voltage_v)
                            except (ValueError, TypeError):
                                _LOGGER.debug("Voltage probe ID %d at OID %s has non-numeric value: %s", probe_id, test_oid, value)
                    
                except Exception as exc:
                    _LOGGER.debug("Error testing voltage probe OID %s: %s", test_oid, exc)
                    continue

        _LOGGER.info("Voltage probe discovery for %s found %d PSU voltage sensors: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering voltage probes for OID %s: %s", base_oid, exc)
    
    return results


async def _discover_memory_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover memory module health sensors."""
    results = []
    
    try:
        _LOGGER.debug("Testing memory health OIDs for base: %s", base_oid)
        
        # Test up to 24 memory slots and also try some common indices
        # Some systems start at different indices
        test_indices = list(range(1, 25)) + [26, 27, 28, 29, 30, 31, 32]
        for memory_id in test_indices:
            test_oid = f"{base_oid}.{memory_id}"
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(test_oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = var_binds[0][1]
                    value_str = str(value).strip()
                    if (value is not None 
                        and value_str  # Must have some content
                        and "No Such Object" not in value_str
                        and "No Such Instance" not in value_str
                        and "noSuchObject" not in value_str
                        and "noSuchInstance" not in value_str):
                        try:
                            # Memory health status should be a valid integer
                            # Accept a very wide range as different iDRAC versions use different values
                            health_value = int(value)
                            if 0 <= health_value <= 255:  # Very broad range to catch any valid responses
                                results.append(memory_id)
                                _LOGGER.debug("Found memory module ID %d at OID %s with health: %s", memory_id, test_oid, value)
                            else:
                                _LOGGER.debug("Memory module ID %d at OID %s has out-of-range health: %s", memory_id, test_oid, value)
                        except (ValueError, TypeError):
                            # Some systems might return text values, so let's accept those too
                            if len(value_str) < 100 and not value_str.lower().startswith('no such'):  # Basic sanity check
                                results.append(memory_id)
                                _LOGGER.debug("Found memory module ID %d at OID %s with text health: %s", memory_id, test_oid, value)
                            else:
                                _LOGGER.debug("Memory module ID %d at OID %s has invalid health: %s", memory_id, test_oid, value)
                    else:
                        _LOGGER.debug("Memory module ID %d at OID %s has invalid health: %s", memory_id, test_oid, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing memory OID %s: %s", test_oid, exc)
                continue

        _LOGGER.info("Memory discovery for %s found %d memory modules: %s", base_oid, len(results), results)
        results.sort()
        
    except Exception as exc:
        _LOGGER.warning("Error discovering memory modules for OID %s: %s", base_oid, exc)
    
    return results


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dell iDRAC."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.info("iDRAC config flow step_user called with input: %s", user_input is not None)
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.info("Calling validate_input with data: %s", {k: v for k, v in user_input.items() if k != CONF_COMMUNITY})
                info = await validate_input(self.hass, user_input)
                _LOGGER.info("validate_input completed successfully")
            except CannotConnect as exc:
                _LOGGER.error("Cannot connect to iDRAC: %s", exc)
                errors["base"] = "cannot_connect"
            except InvalidAuth as exc:
                _LOGGER.error("Invalid authentication for iDRAC: %s", exc)
                errors["base"] = "invalid_auth"
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during validation: %s", exc)
                errors["base"] = "unknown"
            else:
                unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                # Add discovered sensor info to the config data
                config_data = user_input.copy()
                config_data[CONF_DISCOVERED_FANS] = info[CONF_DISCOVERED_FANS]
                config_data[CONF_DISCOVERED_CPUS] = info[CONF_DISCOVERED_CPUS]
                config_data[CONF_DISCOVERED_PSUS] = info[CONF_DISCOVERED_PSUS]
                config_data[CONF_DISCOVERED_VOLTAGE_PROBES] = info[CONF_DISCOVERED_VOLTAGE_PROBES]
                config_data[CONF_DISCOVERED_MEMORY] = info[CONF_DISCOVERED_MEMORY]
                config_data[CONF_DISCOVERED_VIRTUAL_DISKS] = info[CONF_DISCOVERED_VIRTUAL_DISKS]
                config_data[CONF_DISCOVERED_PHYSICAL_DISKS] = info[CONF_DISCOVERED_PHYSICAL_DISKS]
                config_data[CONF_DISCOVERED_STORAGE_CONTROLLERS] = info[CONF_DISCOVERED_STORAGE_CONTROLLERS]
                
                return self.async_create_entry(title=info["title"], data=config_data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Dell iDRAC."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input.get("rediscover_sensors", False):
                # User wants to re-discover sensors
                return await self.async_step_rediscover()
            
            return self.async_create_entry(title="", data=user_input)

        current_scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, 
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_scan_interval
                    ): vol.All(int, vol.Range(min=10, max=300)),
                    vol.Optional("rediscover_sensors", default=False): bool,
                }
            ),
        )

    async def async_step_rediscover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-discover sensors."""
        if user_input is not None:
            # User confirmed re-discovery
            try:
                # Re-run sensor discovery using existing connection info
                info = await validate_input(self.hass, self._config_entry.data)
                
                # Update the config entry with new discovery data
                new_data = self._config_entry.data.copy()
                new_data[CONF_DISCOVERED_FANS] = info[CONF_DISCOVERED_FANS]
                new_data[CONF_DISCOVERED_CPUS] = info[CONF_DISCOVERED_CPUS]
                new_data[CONF_DISCOVERED_PSUS] = info[CONF_DISCOVERED_PSUS]
                new_data[CONF_DISCOVERED_VOLTAGE_PROBES] = info[CONF_DISCOVERED_VOLTAGE_PROBES]
                new_data[CONF_DISCOVERED_MEMORY] = info[CONF_DISCOVERED_MEMORY]
                new_data[CONF_DISCOVERED_VIRTUAL_DISKS] = info[CONF_DISCOVERED_VIRTUAL_DISKS]
                new_data[CONF_DISCOVERED_PHYSICAL_DISKS] = info[CONF_DISCOVERED_PHYSICAL_DISKS]
                new_data[CONF_DISCOVERED_STORAGE_CONTROLLERS] = info[CONF_DISCOVERED_STORAGE_CONTROLLERS]
                
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data
                )
                
                # Get current options
                current_options = self._config_entry.options.copy()
                
                return self.async_create_entry(title="", data=current_options)
                
            except CannotConnect:
                return self.async_show_form(
                    step_id="rediscover",
                    errors={"base": "cannot_connect"},
                    description_placeholders={"error": "Failed to connect to iDRAC"},
                )
            except Exception as exc:
                _LOGGER.exception("Failed to re-discover sensors")
                return self.async_show_form(
                    step_id="rediscover",
                    errors={"base": "unknown"},
                    description_placeholders={"error": str(exc)},
                )

        return self.async_show_form(
            step_id="rediscover",
            data_schema=vol.Schema({}),
            description_placeholders={
                "host": self._config_entry.data[CONF_HOST],
                "fans": len(self._config_entry.data.get(CONF_DISCOVERED_FANS, [])),
                "cpus": len(self._config_entry.data.get(CONF_DISCOVERED_CPUS, [])),
                "psus": len(self._config_entry.data.get(CONF_DISCOVERED_PSUS, [])),
                "voltages": len(self._config_entry.data.get(CONF_DISCOVERED_VOLTAGE_PROBES, [])),
                "memory": len(self._config_entry.data.get(CONF_DISCOVERED_MEMORY, [])),
            },
        )
async def _discover_system_voltages(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover system voltage sensors."""
    results = []
    
    try:
        _LOGGER.debug("Testing system voltage sensors with base OID: %s", base_oid)
        
        # Test specific voltage sensors that we know exist from discovery
        voltage_indices = [1, 2, 3]  # CPU1 VCORE, CPU2 VCORE, System 3.3V
        
        for i in voltage_indices:
            oid = f"{base_oid}.{i}"
            _LOGGER.debug("Testing voltage sensor OID: %s", oid)
            
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = str(var_binds[0][1]).strip()
                    if value and "No Such" not in value and value != "":
                        _LOGGER.debug("Found voltage sensor %d with value: %s", i, value)
                        results.append(i)
                
            except Exception as exc:
                _LOGGER.debug("Error testing voltage sensor OID %s: %s", oid, exc)
                continue
        
        _LOGGER.info("System voltage discovery for %s found %d voltage sensors: %s", base_oid, len(results), results)
        return results
        
    except Exception as exc:
        _LOGGER.warning("Error discovering system voltage sensors for OID %s: %s", base_oid, exc)
        return []


async def _discover_power_consumption_sensors(
    engine: SnmpEngine,
    auth_data: CommunityData | UsmUserData,
    transport_target: UdpTransportTarget,
    context_data: ContextData,
    base_oid: str,
) -> list[int]:
    """Discover power consumption sensors."""
    results = []
    
    try:
        _LOGGER.debug("Testing power consumption sensors with base OID: %s", base_oid)
        
        # Test specific power consumption sensors that we know exist from discovery
        power_indices = [1, 2, 3]  # PSU1, PSU2, System current
        
        for i in power_indices:
            oid = f"{base_oid}.{i}"
            _LOGGER.debug("Testing power consumption sensor OID: %s", oid)
            
            try:
                error_indication, error_status, error_index, var_binds = await getCmd(
                    engine,
                    auth_data,
                    transport_target,
                    context_data,
                    ObjectType(ObjectIdentity(oid)),
                )
                
                if not error_indication and not error_status and var_binds:
                    value = str(var_binds[0][1]).strip()
                    if value and "No Such" not in value and value != "":
                        try:
                            # Validate it's a numeric value
                            int(value)
                            _LOGGER.debug("Found power consumption sensor %d with value: %s", i, value)
                            results.append(i)
                        except ValueError:
                            _LOGGER.debug("Power consumption sensor %d returned non-numeric value: %s", i, value)
                
            except Exception as exc:
                _LOGGER.debug("Error testing power consumption sensor OID %s: %s", oid, exc)
                continue
        
        _LOGGER.info("Power consumption discovery for %s found %d power sensors: %s", base_oid, len(results), results)
        return results
        
    except Exception as exc:
        _LOGGER.warning("Error discovering power consumption sensors for OID %s: %s", base_oid, exc)
        return []