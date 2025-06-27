"""Dell iDRAC Redfish API client."""
from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RedfishError(Exception):
    """Redfish API error."""


class RedfishClient:
    """Dell iDRAC Redfish API client."""

    def __init__(
        self,
        hass,
        host: str,
        username: str,
        password: str,
        port: int = 443,
        verify_ssl: bool = False,
        request_timeout: int = 30,
        session_timeout: int = 45,
    ) -> None:
        """Initialize the Redfish client."""
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.request_timeout = request_timeout
        self.session_timeout = session_timeout
        self.base_url = f"https://{host}:{port}"
        self._session: aiohttp.ClientSession | None = None
        self._ssl_context: ssl.SSLContext | None = None

    async def _get_ssl_context(self) -> ssl.SSLContext | None:
        """Get or create SSL context once and cache it."""
        if not self.verify_ssl and self._ssl_context is None:
            # Create SSL context once and cache it to avoid repeated SSL handshake overhead
            loop = asyncio.get_event_loop()
            ssl_context = await loop.run_in_executor(None, ssl.create_default_context)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            # Optimize SSL for performance
            ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            self._ssl_context = ssl_context
        return self._ssl_context if not self.verify_ssl else None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            # Get SSL context (cached)
            ssl_context = await self._get_ssl_context()
            
            # Optimized connector for SSL performance and connection reuse
            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                limit=20,  # Increase total connection pool size
                limit_per_host=10,  # More connections per host for concurrent requests
                ttl_dns_cache=600,  # Longer DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=120,  # Much longer keep-alive to avoid SSL handshakes
                enable_cleanup_closed=True,
                force_close=False,  # Don't force close connections
                resolver=aiohttp.resolver.AsyncResolver(),  # Use async DNS resolver
            )

            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Connection": "keep-alive",  # Explicit keep-alive header
                },
                timeout=aiohttp.ClientTimeout(
                    total=self.session_timeout, 
                    connect=15, 
                    sock_read=self.request_timeout,
                ),
            )

        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None
            self._ssl_context = None
    
    async def warm_up_connection(self) -> bool:
        """Pre-warm the SSL connection to avoid first-request penalty."""
        try:
            import time
            start_time = time.time()
            
            # Make a lightweight request to establish SSL connection
            session = await self._get_session()
            url = f"{self.base_url}/redfish/v1"
            auth = aiohttp.BasicAuth(self.username, self.password)
            
            async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=10)) as response:
                # Don't need to read the full response, just establish connection
                await response.read()
            
            warm_up_time = time.time() - start_time
            _LOGGER.debug("SSL connection warm-up completed in %.2f seconds", warm_up_time)
            return True
            
        except Exception as exc:
            _LOGGER.debug("SSL connection warm-up failed: %s", exc)
            return False

    async def get(self, path: str) -> dict[str, Any] | None:
        """Make GET request to Redfish API."""
        import time
        start_time = time.time()
        
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as response:
                if response.status == 200:
                    result = await response.json()
                    request_time = time.time() - start_time
                    _LOGGER.debug("GET %s completed in %.2f seconds", path, request_time)
                    return result
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                elif response.status == 403:
                    _LOGGER.warning("GET %s forbidden: insufficient privileges", path)
                    return None
                elif response.status == 404:
                    _LOGGER.debug("GET %s not found: endpoint may not be supported", path)
                    return None
                elif response.status >= 500:
                    request_time = time.time() - start_time
                    _LOGGER.warning("GET %s server error: %s %s (%.2f seconds)", 
                                   path, response.status, response.reason, request_time)
                    return None
                else:
                    request_time = time.time() - start_time
                    _LOGGER.warning("GET %s failed: %s %s (%.2f seconds)", 
                                   path, response.status, response.reason, request_time)
                    return None
        except asyncio.TimeoutError:
            request_time = time.time() - start_time
            _LOGGER.warning("GET %s timed out after %d seconds (actual: %.2f)", 
                           path, self.request_timeout, request_time)
            return None
        except aiohttp.ClientConnectorError as e:
            request_time = time.time() - start_time
            _LOGGER.warning("GET %s connection failed: %s (%.2f seconds)", path, e, request_time)
            return None
        except aiohttp.ClientSSLError as e:
            request_time = time.time() - start_time
            _LOGGER.warning("GET %s SSL error: %s (%.2f seconds)", path, e, request_time)
            return None
        except ConnectionError as e:
            request_time = time.time() - start_time
            _LOGGER.warning("GET %s connection error: %s (%.2f seconds)", path, e, request_time)
            return None
        except Exception as e:
            request_time = time.time() - start_time
            _LOGGER.error("GET %s unexpected error: %s (%.2f seconds)", path, e, request_time)
            return None

    async def post(self, path: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Make POST request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.post(
                url, auth=auth, json=data, timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                if response.status in [200, 202, 204]:
                    if response.content_length and response.content_length > 0:
                        return await response.json()
                    return {"status": "success"}
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                else:
                    _LOGGER.warning("POST %s failed: %s %s", path, response.status, response.reason)
                    try:
                        error_data = await response.json()
                        _LOGGER.warning("Error details: %s", error_data)
                    except:
                        pass
                    return None
        except asyncio.TimeoutError:
            _LOGGER.warning("POST %s timed out", path)
            return None
        except Exception as e:
            _LOGGER.error("POST %s error: %s", path, e)
            return None

    async def get_service_root(self) -> dict[str, Any] | None:
        """Get Redfish service root information."""
        # Try without trailing slash first, then with trailing slash
        result = await self.get("/redfish/v1")
        if result is None:
            result = await self.get("/redfish/v1/")
        return result

    async def get_system_info(self, system_id: str = "System.Embedded.1") -> dict[str, Any] | None:
        """Get system information."""
        return await self.get(f"/redfish/v1/Systems/{system_id}")

    async def get_thermal_info(self, system_id: str = "System.Embedded.1") -> dict[str, Any] | None:
        """Get thermal information (temperatures and fans)."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Thermal")

    async def get_power_info(self, system_id: str = "System.Embedded.1") -> dict[str, Any] | None:
        """Get power information."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Power")

    async def get_manager_info(self, manager_id: str = "iDRAC.Embedded.1") -> dict[str, Any] | None:
        """Get iDRAC manager information."""
        return await self.get(f"/redfish/v1/Managers/{manager_id}")

    async def get_chassis_info(self, system_id: str = "System.Embedded.1") -> dict[str, Any] | None:
        """Get chassis information."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}")

    async def get_power_subsystem(self, system_id: str = "System.Embedded.1") -> dict[str, Any] | None:
        """Get power subsystem information including redundancy."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/PowerSubsystem")

    async def patch(self, path: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """Make PATCH request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.patch(
                url, auth=auth, json=data, timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                if response.status in [200, 202, 204]:
                    if response.content_length and response.content_length > 0:
                        return await response.json()
                    return {"status": "success"}
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                else:
                    _LOGGER.warning("PATCH %s failed: %s %s", path, response.status, response.reason)
                    try:
                        error_data = await response.json()
                        _LOGGER.warning("Error details: %s", error_data)
                    except:
                        pass
                    return None
        except asyncio.TimeoutError:
            _LOGGER.warning("PATCH %s timed out", path)
            return None
        except Exception as e:
            _LOGGER.error("PATCH %s error: %s", path, e)
            return None

    async def set_indicator_led(
        self, state: str, system_id: str = "System.Embedded.1"
    ) -> dict[str, Any] | None:
        """Set system indicator LED state.
        
        Common Dell iDRAC values: 'Blinking', 'Off'
        Standard Redfish values: 'Lit', 'Blinking', 'Off'
        """
        # Map standard states to Dell-specific values
        state_mapping = {
            "Lit": "Blinking",  # Dell typically uses Blinking instead of Lit
            "On": "Blinking",
            "Blinking": "Blinking", 
            "Off": "Off"
        }
        
        mapped_state = state_mapping.get(state, state)
        data = {"IndicatorLED": mapped_state}
        return await self.patch(f"/redfish/v1/Systems/{system_id}", data)

    async def reset_system(
        self, reset_type: str, system_id: str = "System.Embedded.1"
    ) -> dict[str, Any] | None:
        """Reset system with specified type."""
        data = {"ResetType": reset_type}
        return await self.post(f"/redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset", data)

    async def test_connection(self) -> bool:
        """Test connection to iDRAC Redfish API."""
        try:
            _LOGGER.debug("Testing connection to %s (SSL verify: %s)", self.base_url, self.verify_ssl)
            service_root = await self.get_service_root()
            success = service_root is not None
            if success:
                _LOGGER.debug("Connection test successful to %s", self.base_url)
            else:
                _LOGGER.error("Connection test failed - no service root returned from %s", self.base_url)
                _LOGGER.error("Common solutions: 1) Check if iDRAC web interface is accessible at %s", self.base_url)
                _LOGGER.error("                  2) Try port 443 instead of %d", self.port)
                _LOGGER.error("                  3) Disable SSL verification if using self-signed certificates")
            return success
        except Exception as e:
            _LOGGER.error("Connection test failed to %s: %s", self.base_url, e)
            return False

    def get_performance_info(self) -> dict:
        """Get performance configuration information for debugging."""
        return {
            "request_timeout": self.request_timeout,
            "session_timeout": self.session_timeout,
            "verify_ssl": self.verify_ssl,
            "base_url": self.base_url,
            "ssl_context_cached": self._ssl_context is not None,
            "session_active": self._session is not None and not self._session.closed,
            "connection_pool_limit": 20,
            "keepalive_timeout": 120,
        }