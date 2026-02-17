"""
LEDM API Service - Raw HTTP communication for LEDM-based printers (Sirius).

This service handles all HTTP requests to LEDM endpoints.
No Qt or UI dependencies - pure data fetching and returning.
"""
import requests
import urllib3
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Default timeouts
DEFAULT_TIMEOUT = 10
SHORT_TIMEOUT = 5

# XML Namespaces for Sirius LEDM
LEDM_NAMESPACES = {
    'psdyn': 'http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31',
    'ad': 'http://www.hp.com/schemas/imaging/con/ledm/alertdetails/2007/10/31',
    'locid': 'http://www.hp.com/schemas/imaging/con/ledm/localizationids/2007/10/31'
}


class LEDMApiError(Exception):
    """Exception raised for LEDM API errors."""
    pass


class LEDMApiService:
    """
    Service for fetching data from LEDM endpoints (Sirius printers).
    
    LEDM uses HTTP (not HTTPS) and returns XML instead of JSON.
    All methods are synchronous and return raw/parsed data or raise LEDMApiError.
    """
    
    def __init__(self, ip: str):
        """
        Initialize the LEDM API service.
        
        Args:
            ip: The IP address of the printer.
        """
        self.ip = ip
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self.ip = ip
    
    def _get(self, endpoint: str, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
        """
        Perform a GET request to the specified LEDM endpoint.
        
        Args:
            endpoint: The API endpoint path (e.g., '/DevMgmt/ProductStatusDyn.xml')
            timeout: Request timeout in seconds
            
        Returns:
            The response object
            
        Raises:
            LEDMApiError: If the request fails
        """
        # Ensure endpoint has leading slash
        if not endpoint.startswith('/'):
            endpoint = f"/{endpoint}"
        
        # LEDM uses HTTP, not HTTPS
        url = f"http://{self.ip}{endpoint}"
        
        try:
            response = requests.get(url, verify=False, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            raise LEDMApiError("Connection timed out. Check IP address.")
        except requests.exceptions.ConnectionError:
            raise LEDMApiError("Failed to connect to printer.")
        except requests.exceptions.HTTPError as e:
            raise LEDMApiError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise LEDMApiError(f"Request failed: {str(e)}")
    
    # -------------------------------------------------------------------------
    # Alerts API
    # -------------------------------------------------------------------------
    
    def fetch_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetch and parse alerts from ProductStatusDyn.xml.
        
        Returns:
            List of alert dictionaries normalized to common format
            
        Raises:
            LEDMApiError: If the request or parsing fails
        """
        try:
            response = self._get("/DevMgmt/ProductStatusDyn.xml")
            root = ET.fromstring(response.text)
            
            alerts = []
            ns = LEDM_NAMESPACES
            
            for alert in root.findall('.//psdyn:AlertTable/psdyn:Alert', ns):
                details = alert.find('ad:AlertDetails', ns)
                
                # Extract color
                color = ''
                if details is not None:
                    color = details.findtext('ad:AlertDetailsMarkerColor', namespaces=ns, default='')
                
                # Normalize color names
                if color == "CyanMagentaYellow":
                    color = "Tri-Color"
                
                # Extract IDs and error codes
                product_status_id = alert.findtext('ad:ProductStatusAlertID', namespaces=ns, default='')
                original_string_id = alert.findtext('locid:StringId', namespaces=ns, default='')
                error_code = ''
                if details is not None:
                    error_code = details.findtext('ad:AlertDetailsErrorCode', namespaces=ns, default='')
                
                # Prepare badges
                badges = []
                if product_status_id:
                    badges.append(product_status_id)
                if error_code:
                    badges.append(error_code)
                
                # Build normalized alert object
                alerts.append({
                    'id': product_status_id,
                    'stringId': original_string_id,
                    'badges': badges,
                    'category': color if color else 'General',
                    'severity': alert.findtext('ad:Severity', namespaces=ns, default='info'),
                    'priority': alert.findtext('ad:AlertPriority', namespaces=ns, default=''),
                    'raw_color': color,
                    'original_stringId': original_string_id
                })
            
            return alerts
            
        except ET.ParseError as e:
            raise LEDMApiError(f"Failed to parse XML: {str(e)}")
    
    # -------------------------------------------------------------------------
    # Generic Endpoint Fetching
    # -------------------------------------------------------------------------
    
    def fetch_endpoint(self, endpoint: str) -> str:
        """
        Fetch raw XML content from any LEDM endpoint.
        
        Args:
            endpoint: The endpoint path
            
        Returns:
            Raw response text (XML)
            
        Raises:
            LEDMApiError: If the request fails
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
            except LEDMApiError as e:
                results[endpoint] = f"Error: {str(e)}"
            except Exception as e:
                results[endpoint] = f"Error: {str(e)}"
        
        return results
    
    def fetch_endpoint_xml(self, endpoint: str) -> ET.Element:
        """
        Fetch and parse XML from any LEDM endpoint.
        
        Args:
            endpoint: The endpoint path
            
        Returns:
            Parsed XML root element
            
        Raises:
            LEDMApiError: If the request fails or XML is invalid
        """
        response = self._get(endpoint)
        try:
            return ET.fromstring(response.text)
        except ET.ParseError as e:
            raise LEDMApiError(f"Invalid XML response: {str(e)}")


# Common LEDM endpoints
class LEDMEndpoints:
    """Common LEDM endpoint paths."""
    PRODUCT_STATUS = "/DevMgmt/ProductStatusDyn.xml"
    CONSUMABLES = "/DevMgmt/ConsumableConfigDyn.xml"
    PRODUCT_CONFIG = "/DevMgmt/ProductConfigDyn.xml"
    DEVICE_STATUS = "/DevMgmt/DeviceStatusDyn.xml"


# Convenience function for one-off requests
def fetch_ledm_data(ip: str, endpoint: str) -> str:
    """
    Convenience function to fetch data from a single LEDM endpoint.
    
    Args:
        ip: Printer IP address
        endpoint: API endpoint path
        
    Returns:
        Raw response text (XML)
    """
    service = LEDMApiService(ip)
    return service.fetch_endpoint(endpoint)
