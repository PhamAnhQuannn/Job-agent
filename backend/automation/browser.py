"""Browser manager for Playwright with stealth and human-like behavior."""

import asyncio
import os
import re
import random
import logging
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# DRY_RUN: if true, navigate but don't click submit
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


async def random_delay(min_ms: int = 500, max_ms: int = 2000):
    """Human-like random delay."""
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)


async def create_browser() -> tuple[Browser, BrowserContext]:
    """Launch a stealth Chromium instance."""
    pw = await async_playwright().start()

    browser = await pw.chromium.launch(
        headless=HEADLESS,
        slow_mo=500 if not HEADLESS else 0,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/Los_Angeles",
    )

    # Stealth: remove webdriver flag
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
    """)

    return browser, context


async def take_screenshot(page: Page, company: str, location: str = "") -> str:
    """Capture a screenshot and return the file path."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_company = re.sub(r'[^\w\-]', '_', company.strip())[:50]
    safe_location = re.sub(r'[^\w\-]', '_', location.strip())[:50] if location else "remote"
    filename = f"{safe_company}_{safe_location}_{ts}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)
    await page.screenshot(path=path, full_page=False)
    logger.info(f"Screenshot saved: {path}")
    return filename


async def human_type(page: Page, selector: str, text: str):
    """Type text with human-like delays between keystrokes."""
    await page.click(selector)
    await random_delay(200, 500)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(30, 120))
    await random_delay(300, 800)


async def human_click(page: Page, selector: str):
    """Click an element with a random delay before and after."""
    await random_delay(300, 800)
    await page.click(selector)
    await random_delay(500, 1500)
