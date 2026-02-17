"""
CDM API Service - Raw HTTP communication for CDM-based printers.

This service handles all HTTP requests to CDM endpoints (Dune, Ares).
No Qt or UI dependencies - pure data fetching and returning.
"""
import requests
import urllib3
from typing import Dict, List, Optional, Any, Tuple

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default timeouts
DEFAULT_TIMEOUT = 10
SHORT_TIMEOUT = 5


class CDMApiError(Exception):
    """Exception raised for CDM API errors."""
    pass


class CDMApiService:
    """
    Service for fetching data from CDM endpoints.
    
    All methods are synchronous and return raw data or raise CDMApiError.
    Thread safety: This class is stateless and thread-safe.
    """
    
    def __init__(self, ip: str):
        """
        Initialize the CDM API service.
        
        Args:
            ip: The IP address of the printer.
        """
        self.ip = ip
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self.ip = ip
    
    def _get(self, endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
        """
        Perform a GET request to the specified endpoint.
        
        Args:
            endpoint: The API endpoint path (e.g., 'cdm/alert/v1/alerts')
            timeout: Request timeout in seconds
            
        Returns:
            The response object
            
        Raises:
            CDMApiError: If the request fails
        """
        # Ensure endpoint doesn't have leading slash for consistent URL building
        endpoint = endpoint.lstrip('/')
        url = f"https://{self.ip}/{endpoint}"
        
        try:
            response = requests.get(url, verify=False, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            raise CDMApiError("Connection timed out. Check IP address.")
        except requests.exceptions.ConnectionError:
            raise CDMApiError("Failed to connect to printer.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise CDMApiError("Unauthorized (401): Authentication required.")
            raise CDMApiError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise CDMApiError(f"Request failed: {str(e)}")
    
    def _put(self, endpoint: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
        """
        Perform a PUT request to the specified endpoint.
        
        Args:
            endpoint: The API endpoint path
            payload: JSON payload to send
            timeout: Request timeout in seconds
            
        Returns:
            The response object
            
        Raises:
            CDMApiError: If the request fails
        """
        endpoint = endpoint.lstrip('/')
        url = f"https://{self.ip}/{endpoint}"
        
        try:
            response = requests.put(url, json=payload, verify=False, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            raise CDMApiError("Connection timed out.")
        except requests.exceptions.ConnectionError:
            raise CDMApiError("Failed to connect to printer.")
        except Exception as e:
            raise CDMApiError(f"Request failed: {str(e)}")
    
    # -------------------------------------------------------------------------
    # Alerts API
    # -------------------------------------------------------------------------
    
    def fetch_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetch alerts from the printer.
        
        Returns:
            List of alert dictionaries
            
        Raises:
            CDMApiError: If the request fails
        """
        response = self._get("cdm/alert/v1/alerts", timeout=SHORT_TIMEOUT)
        data = response.json()
        
        # Normalize response to list
        if isinstance(data, dict):
            if 'alerts' in data:
                return data['alerts']
            elif 'elements' in data:
                return data['elements']
            elif any(key in data for key in ['stringId', 'category', 'severity', 'id']):
                return [data]
            else:
                return []
        
        return data if isinstance(data, list) else []
    
    def send_alert_action(self, alert_id: int, action: str) -> bool:
        """
        Send an action for a specific alert.
        
        Args:
            alert_id: The alert ID
            action: The action to perform (e.g., 'acknowledge', 'continue')
            
        Returns:
            True if successful
            
        Raises:
            CDMApiError: If the request fails
        """
        # Handle legacy 'continue_' value
        if action == "continue_":
            action = "continue"
        
        payload = {"selectedAction": action}
        self._put(f"cdm/supply/v1/alerts/{alert_id}/action", payload)
        return True
    
    # -------------------------------------------------------------------------
    # Telemetry API
    # -------------------------------------------------------------------------
    
    def fetch_telemetry_events(self) -> List[Dict[str, Any]]:
        """
        Fetch telemetry/supply events from the printer.
        
        Returns:
            List of telemetry event dictionaries
            
        Raises:
            CDMApiError: If the request fails
        """
        response = self._get("cdm/eventing/v1/events/supply", timeout=SHORT_TIMEOUT)
        data = response.json()
        
        # Normalize response to list
        if isinstance(data, dict):
            if 'events' in data:
                return data['events']
            elif any(key in data for key in ['sequenceNumber', 'eventDetail']):
                return [data]
            else:
                return []
        
        return data if isinstance(data, list) else []
    
    # -------------------------------------------------------------------------
    # Generic Endpoint Fetching
    # -------------------------------------------------------------------------
    
    def fetch_endpoint(self, endpoint: str) -> str:
        """
        Fetch raw text content from any CDM endpoint.
        
        Args:
            endpoint: The endpoint path
            
        Returns:
            Raw response text
            
        Raises:
            CDMApiError: If the request fails
        """
        response = self._get(endpoint)
        return response.text
    
    def fetch_endpoints(self, endpoints: List[str]) -> Dict[str, str]:
        """
        Fetch multiple endpoints and return results.
        
        Args:
            endpoints: List of endpoint paths
            
        Returns:
            Dict mapping endpoint to response text (or error message)
        """
        results = {}
        
        for endpoint in endpoints:
            try:
                results[endpoint] = self.fetch_endpoint(endpoint)
            except CDMApiError as e:
                results[endpoint] = f"Error: {str(e)}"
            except Exception as e:
                results[endpoint] = f"Error: {str(e)}"
        
        return results
    
    def fetch_endpoint_json(self, endpoint: str) -> Any:
        """
        Fetch and parse JSON from any CDM endpoint.
        
        Args:
            endpoint: The endpoint path
            
        Returns:
            Parsed JSON data
            
        Raises:
            CDMApiError: If the request fails or JSON is invalid
        """
        response = self._get(endpoint)
        try:
            return response.json()
        except ValueError as e:
            raise CDMApiError(f"Invalid JSON response: {str(e)}")


# Convenience function for one-off requests
def fetch_cdm_data(ip: str, endpoint: str) -> str:
    """
    Convenience function to fetch data from a single endpoint.
    
    Args:
        ip: Printer IP address
        endpoint: API endpoint path
        
    Returns:
        Raw response text
    """
    service = CDMApiService(ip)
    return service.fetch_endpoint(endpoint)
