"""
scraper/flipkart_scraper.py
Async Playwright-based scraper for Flipkart laptop listings.

⚠️  LEGAL NOTE: Scraping Flipkart violates their Terms of Service (Section 7).
    This implementation is provided for educational/portfolio purposes only.
    For production use, consider the Flipkart Affiliate API (free registration).
    Rate limiting, randomised delays, and caching are used to be respectful.

Usage:
    import asyncio
    from scraper.flipkart_scraper import scrape_flipkart
    results = asyncio.run(scrape_flipkart("i5 16gb laptop", max_results=10))
"""

import asyncio
import re
import random
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Playwright is optional — if not installed, the scraper silently falls back
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("[Scraper] playwright not installed. Live scraping disabled.")

# ─── Constants ────────────────────────────────────────────────────────────────
FLIPKART_SEARCH_URL = "https://www.flipkart.com/search?q={query}&otracker=search&as-show=on&as=off"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}
MIN_DELAY = 1.5   # seconds between requests
MAX_DELAY = 4.0


def _product_id(name: str, source: str = "flipkart") -> str:
    """Stable short hash for a product."""
    return hashlib.md5(f"{name.lower()}::{source}".encode()).hexdigest()[:12]


def _parse_price(text: str) -> Optional[float]:
    """Extract numeric price from strings like '₹54,990' or 'Rs. 54,990'."""
    digits = re.sub(r"[^\d]", "", text)
    return float(digits) if digits else None


async def _scrape_page(page, url: str) -> list[dict]:
    """
    Navigate to a Flipkart search URL and extract laptop cards.
    Returns a list of raw product dicts.
    """
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # Random human-like delay
    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    products = []

    # Flipkart renders product cards in divs with data-id attribute
    # Selectors may break if Flipkart updates their layout
    cards = await page.query_selector_all("div[data-id]")

    for card in cards:
        try:
            # Product name
            name_el = await card.query_selector("a.s1Q9rs, div.KzDlHZ, a._2UzuFa")
            if not name_el:
                continue
            name = (await name_el.inner_text()).strip()

            # Price
            price_el = await card.query_selector("div._30jeq3, div.Nx9bqj")
            price_text = await price_el.inner_text() if price_el else ""
            price = _parse_price(price_text)
            if not price:
                continue

            # Product link
            link_el = await card.query_selector("a._1fQZEK, a.s1Q9rs, a._2UzuFa")
            href = await link_el.get_attribute("href") if link_el else ""
            buy_url = f"https://www.flipkart.com{href}" if href.startswith("/") else href

            # Image
            img_el = await card.query_selector("img._396cs4, img.DByuf4")
            image_url = await img_el.get_attribute("src") if img_el else ""

            product_id = _product_id(name)
            products.append({
                "product_id": product_id,
                "name":       name,
                "price":      price,
                "buy_url":    buy_url,
                "image_url":  image_url,
                "seller":     "Flipkart",
                "source":     "flipkart",
            })

        except Exception as e:
            logger.debug(f"[Scraper] Skipping card: {e}")
            continue

    return products


async def scrape_flipkart(
    query: str,
    max_results: int = 10,
    predicted_price: Optional[float] = None,
    confidence_band: float = 10000,
) -> list[dict]:
    """
    Scrape Flipkart for laptop listings matching `query`.

    Args:
        query:            Search string e.g. "Intel i5 16GB laptop"
        max_results:      Maximum number of listings to return
        predicted_price:  If provided, compute price-band match flags
        confidence_band:  ±INR tolerance for in_band flag

    Returns:
        List of product dicts, or empty list if scraping fails.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("[Scraper] Playwright unavailable — returning empty list.")
        return []

    url = FLIPKART_SEARCH_URL.format(query=query.replace(" ", "+"))
    results = []

    try:
        async with async_playwright() as pw:
            # Launch headless Chromium with stealth-like settings
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                ],
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="en-IN",
                extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
                viewport={"width": 1366, "height": 768},
            )
            # Mask automation signals
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            results = await _scrape_page(page, url)

            # If first page has fewer results, try page 2
            if len(results) < max_results:
                page2_url = url + "&page=2"
                results.extend(await _scrape_page(page, page2_url))

            await browser.close()

    except PlaywrightTimeout:
        logger.warning("[Scraper] Flipkart request timed out.")
    except Exception as e:
        logger.error(f"[Scraper] Unexpected error: {e}")

    # Trim and annotate
    results = results[:max_results]
    for r in results:
        if predicted_price:
            r["in_band"]    = abs(r["price"] - predicted_price) <= confidence_band
            r["match_score"] = max(0, 100 - int(abs(r["price"] - predicted_price) / 500))

    return results
