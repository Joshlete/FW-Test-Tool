import asyncio
from playwright.async_api import async_playwright
import io
from PIL import Image

class WebpageScreenshotCapture:
    """
    A class dedicated to capturing screenshots of a webpage's expandable panels.
    """
    def __init__(self, viewport_width=1920, viewport_height=1080,
                 clip_top=0, clip_bottom=0, clip_left=0, clip_right=0):
        print("[DEBUG][WebpageScreenshotCapture] Initializing with parameters:")
        print(f"[DEBUG][WebpageScreenshotCapture] viewport_width={viewport_width}, viewport_height={viewport_height}, "
              f"clip_top={clip_top}, clip_bottom={clip_bottom}, clip_left={clip_left}, clip_right={clip_right}")
        
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.clip_top = clip_top
        self.clip_bottom = clip_bottom
        self.clip_left = clip_left
        self.clip_right = clip_right

    async def _fetch_screenshots(self, url: str):
        """
        Asynchronously capture and return a list of clipped screenshots of all expanded panels.
        Simulates zooming out to 60% by setting document.body.style.zoom before capturing.
        """
        print(f"[DEBUG][WebpageScreenshotCapture] Starting _fetch_screenshots for URL: {url}")
        async with async_playwright() as p:
            print("[DEBUG][WebpageScreenshotCapture] Launching browser...")
            browser = await p.chromium.launch()
            print("[DEBUG][WebpageScreenshotCapture] Creating browser context with provided viewport settings.")
            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={"width": self.viewport_width, "height": self.viewport_height}
            )
            page = await context.new_page()

            # Ensure URL starts with a proper protocol
            if not url.startswith(('http://', 'https://')):
                print("[DEBUG][WebpageScreenshotCapture] URL missing protocol, adding 'https://'")
                url = 'https://' + url

            print(f"[DEBUG][WebpageScreenshotCapture] Navigating to URL: {url}")
            await page.goto(url, wait_until='networkidle')
            print("[DEBUG][WebpageScreenshotCapture] Page loaded successfully.")

            print("[DEBUG][WebpageScreenshotCapture] Searching for notifications button...")
            notification_button = await page.wait_for_selector('button[aria-label="Notifications"]')
            await notification_button.click()
            print("[DEBUG][WebpageScreenshotCapture] Notifications button clicked.")

            # Allow the panel to load
            print("[DEBUG][WebpageScreenshotCapture] Waiting for panels to load...")
            await page.wait_for_timeout(1000)

            print("[DEBUG][WebpageScreenshotCapture] Making accordion multi-expandable...")
            await page.evaluate('''() => {
                const accordion = document.querySelector('mat-accordion');
                if (accordion) {
                    accordion.setAttribute('multi', '');
                    accordion.setAttribute('ng-reflect-multi', 'true');
                }
            }''')

            print("[DEBUG][WebpageScreenshotCapture] Selecting all expansion panel headers...")
            expansion_panels = await page.query_selector_all('mat-expansion-panel-header')
            print(f"[DEBUG][WebpageScreenshotCapture] Found {len(expansion_panels)} panels.")
            images = []

            if not expansion_panels:
                print("[DEBUG][WebpageScreenshotCapture] No expansion panels found. Capturing full page screenshot...")
                full_screenshot = await page.screenshot(full_page=True)
                
                image = Image.open(io.BytesIO(full_screenshot))
                clip_box = (
                    self.clip_left,
                    self.clip_top,
                    image.width - self.clip_right,
                    image.height - self.clip_bottom
                )
                print(f"[DEBUG][WebpageScreenshotCapture] Clipping image with box: {clip_box}")
                clipped_image = image.crop(clip_box)
                images.append(clipped_image)
                print("[DEBUG][WebpageScreenshotCapture] Base screenshot captured and clipped.")
            else:
                for index, panel in enumerate(expansion_panels):
                    print(f"[DEBUG][WebpageScreenshotCapture] Clicking panel {index + 1} of {len(expansion_panels)}...")
                    await panel.click()
                    await page.wait_for_timeout(200)  # Small delay

                    print(f"[DEBUG][WebpageScreenshotCapture] Capturing full page screenshot for panel {index + 1}...")
                    full_screenshot = await page.screenshot(full_page=True)
                    
                    image = Image.open(io.BytesIO(full_screenshot))
                    clip_box = (
                        self.clip_left,
                        self.clip_top,
                        image.width - self.clip_right,
                        image.height - self.clip_bottom
                    )
                    print(f"[DEBUG][WebpageScreenshotCapture] Clipping image with box: {clip_box}")
                    clipped_image = image.crop(clip_box)
                    images.append(clipped_image)
                    print(f"[DEBUG][WebpageScreenshotCapture] Panel {index + 1} screenshot captured and clipped.")

            await page.wait_for_timeout(1000)
            print("[DEBUG][WebpageScreenshotCapture] Closing browser.")
            await browser.close()

            print("[DEBUG][WebpageScreenshotCapture] Returning list of clipped images.")
            return images

    def capture_screenshots(self, url: str):
        """
        Public method to capture screenshots synchronously by running the async loop.
        Returns a list of PIL Image objects.
        """
        print("[DEBUG][WebpageScreenshotCapture] capture_screenshots called.")
        print(f"[DEBUG][WebpageScreenshotCapture] Running asynchronous capture for URL: {url}")
        result = asyncio.run(self._fetch_screenshots(url))
        print(f"[DEBUG][WebpageScreenshotCapture] capture_screenshots completed, returning {len(result)} images.")
        return result
