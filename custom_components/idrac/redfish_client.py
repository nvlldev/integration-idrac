"""Dell iDRAC Redfish API client."""
from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any, Dict, Optional

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
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            # Create our own session since we need custom SSL settings
            if self.verify_ssl:
                connector = aiohttp.TCPConnector()
            else:
                # Disable SSL verification for older iDRACs
                # Use executor to avoid blocking the event loop
                import functools
                loop = asyncio.get_event_loop()
                ssl_context = await loop.run_in_executor(None, ssl.create_default_context)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)

            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.session_timeout, connect=15),
            )

        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def get(self, path: str) -> Optional[Dict[str, Any]]:
        """Make GET request to Redfish API."""
        url = f"{self.base_url}{path}"
        auth = aiohttp.BasicAuth(self.username, self.password)

        try:
            session = await self._get_session()
            async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=self.request_timeout)) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    raise RedfishError("Authentication failed - check credentials")
                else:
                    _LOGGER.warning("GET %s failed: %s %s", path, response.status, response.reason)
                    return None
        except asyncio.TimeoutError:
            _LOGGER.warning("GET %s timed out after %d seconds", path, self.request_timeout)
            return None
        except Exception as e:
            _LOGGER.error("GET %s error: %s", path, e)
            return None

    async def post(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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

    async def get_service_root(self) -> Optional[Dict[str, Any]]:
        """Get Redfish service root information."""
        # Try without trailing slash first, then with trailing slash
        result = await self.get("/redfish/v1")
        if result is None:
            result = await self.get("/redfish/v1/")
        return result

    async def get_system_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get system information."""
        return await self.get(f"/redfish/v1/Systems/{system_id}")

    async def get_thermal_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get thermal information (temperatures and fans)."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Thermal")

    async def get_power_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get power information."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/Power")

    async def get_manager_info(self, manager_id: str = "iDRAC.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get iDRAC manager information."""
        return await self.get(f"/redfish/v1/Managers/{manager_id}")

    async def get_chassis_info(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get chassis information."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}")

    async def get_power_subsystem(self, system_id: str = "System.Embedded.1") -> Optional[Dict[str, Any]]:
        """Get power subsystem information including redundancy."""
        return await self.get(f"/redfish/v1/Chassis/{system_id}/PowerSubsystem")

    async def patch(self, path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    ) -> Optional[Dict[str, Any]]:
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
    ) -> Optional[Dict[str, Any]]:
        """Reset system with specified type."""
        data = {"ResetType": reset_type}
        return await self.post(f"/redfish/v1/Systems/{system_id}/Actions/ComputerSystem.Reset", data)

    async def test_connection(self) -> bool:
        """Test connection to iDRAC Redfish API."""
        try:
            _LOGGER.debug("Testing connection to %s", self.base_url)
            service_root = await self.get_service_root()
            success = service_root is not None
            if success:
                _LOGGER.debug("Connection test successful to %s", self.base_url)
            else:
                _LOGGER.error("Connection test failed - no service root returned from %s", self.base_url)
            return success
        except Exception as e:
            _LOGGER.error("Connection test failed to %s: %s", self.base_url, e)
            return False