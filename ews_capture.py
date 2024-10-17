import os
import io
from PIL import Image
from playwright.sync_api import sync_playwright
import tkinter as tk
from tkinter import ttk, filedialog
import concurrent.futures
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class EWSScreenshotCapturer:
    def __init__(self, parent_frame, ip_address, directory):
        self.parent_frame = parent_frame
        self.ip_address = ip_address
        self.manhattan_printer_info_page = os.getenv('MANHATTAN_PRINTER_INFO_PATH')
        self.manhattan_supplies_page = os.getenv('MANHATTAN_SUPPLIES_PATH')
        print(f"    >> Initializing EWSScreenshotCapturer for IP: {ip_address}")

    def capture_screenshots(self, number):
        """Main method to capture and save EWS screenshots."""
        print("    >> Starting screenshot capture process")
        try:
            results = self._capture_ews_screenshots()
            if results:
                print("    >> Screenshots captured successfully, proceeding to save")
                self._save_ews_screenshots(results, number)
                return True, "EWS screenshots captured successfully"
            print("    >> Failed to capture screenshots")
            return False, "Failed to capture EWS screenshots"
        except Exception as e:
            print(f"    >> Error occurred: {str(e)}")
            return False, f"Error capturing EWS screenshot: {str(e)}"

    def _capture_ews_screenshots(self):
        """Capture screenshots of specified EWS pages."""
        print("    >> Starting to capture EWS screenshots")
        print(f"    >> IP address provided: {self.ip_address}")
        if not self.ip_address:
            print("    >> No IP address provided, aborting")
            return None

        def capture_page(url, description, crop_amounts):
            """Capture and crop a single page screenshot."""
            print(f"    >> Capturing page: {description}")
            with sync_playwright() as p:
                print("    >> Launching browser")
                browser = p.chromium.launch()
                page = browser.new_page(ignore_https_errors=True)
                print(f"    >> Navigating to {url}")
                page.goto(url)
                page.wait_for_load_state('networkidle')

                # Remove the 'btn-list' div
                print("    >> Removing 'btn-list' div")
                page.evaluate("""
                    () => {
                        const btnList = document.querySelector('.btn-list');
                        if (btnList) {
                            btnList.remove();
                        }
                    }
                """)

                print("    >> Taking screenshot")
                screenshot = page.screenshot(full_page=True)
                image = Image.open(io.BytesIO(screenshot))
                
                # Crop the image
                print("    >> Cropping image")
                left, upper, right, lower = crop_amounts
                right = image.width - right
                lower = image.height - lower
                cropped_image = image.crop((left, upper, right, lower))
                
                # Convert cropped image to bytes
                print("    >> Converting image to bytes")
                cropped_image_bytes = io.BytesIO()
                cropped_image.save(cropped_image_bytes, format='PNG')
                return cropped_image_bytes.getvalue(), description

        # Define URLs and crop settings for each page
        urls = [
            (f'https://{self.ip_address}/{self.manhattan_printer_info_page}', "EWS Printer Information", (150, 0, 150, 180)),
            (f'https://{self.ip_address}/{self.manhattan_supplies_page}', "EWS Supply Status", (150, 0, 150, 500))
        ]

        print("    >> Capturing all specified pages concurrently")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as executor:
            future_to_url = {executor.submit(capture_page, url, description, crop_amounts): (url, description) for url, description, crop_amounts in urls}
            results = []
            for future in concurrent.futures.as_completed(future_to_url):
                url, description = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                    print(f"    >> Captured: {description}")
                except Exception as exc:
                    print(f"    >> Error capturing {description}: {exc}")
        
        return results

    def _save_ews_screenshots(self, results, number):
        """Save captured screenshots to the specified directory."""
        print("    >> Starting to save screenshots")
        
        print(f"    >> Using directory: {self.directory}")
        
        for screenshot, description in results:
            filename = f"{number}. {description}.png" if number else f"{description}.png"
            filepath = os.path.join(self.directory, filename)
            
            try:
                print(f"    >> Saving file: {filepath}")
                with open(filepath, 'wb') as f:
                    f.write(screenshot)
                print(f"    >> File saved successfully: {filepath}")
            except IOError as e:
                print(f"    >> Error saving file {filepath}: {str(e)}")