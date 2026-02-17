"""
EWS Service - Screenshot capture from Embedded Web Server.

This service handles browser automation to capture EWS page screenshots.
No Qt or UI dependencies - pure capture and return.
"""
import os
import io
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image

# Playwright is imported at runtime to allow graceful failure
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class EWSServiceError(Exception):
    """Exception raised for EWS service errors."""
    pass


class EWSService:
    """
    Service for capturing EWS (Embedded Web Server) screenshots.
    
    Uses Playwright for browser automation. All methods are synchronous.
    """
    
    # Default crop amounts: (left, top, right, bottom)
    DEFAULT_CROPS = {
        "printer_info": (150, 0, 150, 180),
        "supply_status": (150, 0, 150, 170),
    }
    
    # Default EWS pages to capture
    DEFAULT_PAGES = [
        {"url_path": "#hId-pgDevInfo", "name": "EWS Printer Information", "crop": "printer_info"},
        {"url_path": "#hId-pgConsumables", "name": "EWS Supply Status", "crop": "supply_status"},
    ]
    
    def __init__(self, ip: str, password: str = ""):
        """
        Initialize the EWS service.
        
        Args:
            ip: The IP address of the printer.
            password: Admin password for EWS authentication (optional).
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise EWSServiceError("Playwright is not installed. Run: pip install playwright && playwright install")
        
        self.ip = ip
        self.password = password
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self.ip = ip
    
    def set_password(self, password: str) -> None:
        """Update the EWS password."""
        self.password = password
    
    def capture_page(
        self,
        url_path: str,
        crop_amounts: Optional[Tuple[int, int, int, int]] = None,
        timeout: int = 60000
    ) -> bytes:
        """
        Capture a screenshot of an EWS page.
        
        Args:
            url_path: The path/hash portion of the URL (e.g., '#hId-pgDevInfo')
            crop_amounts: Optional (left, top, right, bottom) crop amounts
            timeout: Page load timeout in milliseconds
            
        Returns:
            PNG image bytes
            
        Raises:
            EWSServiceError: If capture fails
        """
        url = f"https://{self.ip}/{url_path}"
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                
                # Create context with HTTP credentials
                context = browser.new_context(
                    ignore_https_errors=True,
                    http_credentials={
                        "username": "admin",
                        "password": self.password
                    }
                )
                
                page = context.new_page()
                page.goto(url, timeout=timeout)
                page.wait_for_load_state('networkidle')
                
                # Remove UI elements that shouldn't be in screenshot
                page.evaluate("""
                    () => {
                        const btnList = document.querySelector('.btn-list');
                        if (btnList) {
                            btnList.remove();
                        }
                    }
                """)
                
                # Take screenshot
                screenshot = page.screenshot(full_page=True)
                
                # Crop if specified
                if crop_amounts:
                    image = Image.open(io.BytesIO(screenshot))
                    left, upper, right, lower = crop_amounts
                    right = image.width - right
                    lower = image.height - lower
                    cropped = image.crop((left, upper, right, lower))
                    
                    # Convert back to bytes
                    output = io.BytesIO()
                    cropped.save(output, format='PNG')
                    screenshot = output.getvalue()
                
                context.close()
                browser.close()
                
                return screenshot
                
        except Exception as e:
            raise EWSServiceError(f"Failed to capture EWS page: {str(e)}")
    
    def capture_default_pages(self) -> List[Tuple[bytes, str]]:
        """
        Capture all default EWS pages.
        
        Returns:
            List of (image_bytes, page_name) tuples
            
        Raises:
            EWSServiceError: If any capture fails
        """
        results = []
        
        for page_config in self.DEFAULT_PAGES:
            url_path = page_config["url_path"]
            name = page_config["name"]
            crop_key = page_config.get("crop")
            crop_amounts = self.DEFAULT_CROPS.get(crop_key) if crop_key else None
            
            try:
                screenshot = self.capture_page(url_path, crop_amounts)
                results.append((screenshot, name))
            except EWSServiceError:
                raise
        
        return results
    
    def capture_and_save(
        self,
        directory: str,
        prefix: str = "",
        pages: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Capture pages and save them to files.
        
        Args:
            directory: Directory to save screenshots
            prefix: Optional prefix for filenames (e.g., "1. ")
            pages: Optional list of page configs. Uses DEFAULT_PAGES if not provided.
            
        Returns:
            List of saved file paths
            
        Raises:
            EWSServiceError: If capture or save fails
        """
        if not os.path.exists(directory):
            raise EWSServiceError(f"Directory does not exist: {directory}")
        
        pages = pages or self.DEFAULT_PAGES
        saved_files = []
        
        for page_config in pages:
            url_path = page_config["url_path"]
            name = page_config["name"]
            crop_key = page_config.get("crop")
            crop_amounts = self.DEFAULT_CROPS.get(crop_key) if crop_key else None
            
            try:
                screenshot = self.capture_page(url_path, crop_amounts)
                
                filename = f"{prefix}{name}.png" if prefix else f"{name}.png"
                filepath = os.path.join(directory, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(screenshot)
                
                saved_files.append(filepath)
                
            except Exception as e:
                raise EWSServiceError(f"Failed to capture/save {name}: {str(e)}")
        
        return saved_files


# Convenience function for one-off captures
def capture_ews_screenshot(ip: str, url_path: str, password: str = "") -> bytes:
    """
    Convenience function to capture a single EWS page.
    
    Args:
        ip: Printer IP address
        url_path: URL path/hash to capture
        password: Optional admin password
        
    Returns:
        PNG image bytes
    """
    service = EWSService(ip, password)
    return service.capture_page(url_path)
