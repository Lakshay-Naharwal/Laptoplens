"""
scraper/image_fetcher.py
=========================
Selenium-based laptop product image fetcher.
Searches Flipkart for the laptop name, grabs the first product image URL,
caches results in scraper/image_cache.json so Selenium only runs once per model.

Usage:
    # In code
    from backend.scraper.image_fetcher import get_image
    url = get_image("ASUS ROG Strix G15")

    # Pre-warm cache for all 22 mock catalogue models
    python scraper/image_fetcher.py --prewarm

    # Fetch a single laptop
    python scraper/image_fetcher.py --name "Dell XPS 15"
"""

import argparse
import json
import logging
import random
import re
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

# ── Cache ────────────────────────────────────────────────────────────────────
_CACHE_PATH = Path(__file__).parent / "image_cache.json"
_cache_lock = threading.Lock()


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    with _cache_lock:
        _CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


# ── SVG placeholder ──────────────────────────────────────────────────────────
def _placeholder_svg(name: str) -> str:
    """Return a branded SVG data-URL when all else fails."""
    label = name[:20].replace('"', "'")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">'
        '<rect width="300" height="200" fill="#1e293b"/>'
        '<text x="150" y="90" font-family="Arial" font-size="36" '
        'fill="#334155" text-anchor="middle">💻</text>'
        f'<text x="150" y="130" font-family="Arial" font-size="11" '
        f'fill="#64748b" text-anchor="middle">{label}</text>'
        "</svg>"
    )
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ── Selenium driver ──────────────────────────────────────────────────────────
def _build_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_argument("--window-size=1280,800")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return driver


# ── Core fetch logic ─────────────────────────────────────────────────────────
def _fetch_flipkart_image(driver, name: str) -> str | None:
    """
    Search Flipkart for the laptop name, return the first product image src.
    Returns None if nothing useful is found.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    query = name.replace(" ", "+")
    url = f"https://www.flipkart.com/search?q={query}&category=6bo%2Fai%2Fdvjc"
    log.info(f"  Fetching image for: {name}")

    try:
        driver.get(url)
        time.sleep(random.uniform(2.0, 4.0))

        # Try multiple known Flipkart image selectors
        for selector in [
            "img._396cs4",   # old layout
            "img.DByuf4",    # new layout 2024
            "img._2r_T1I",
            "div[data-id] img",
        ]:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in els:
                src = el.get_attribute("src") or ""
                # Must be a real image URL (not a tiny icon / base64)
                if src.startswith("https://") and "rukminim" in src and len(src) > 50:
                    # Upgrade to higher resolution
                    src = re.sub(r"/\d+/\d+/", "/416/416/", src)
                    return src

    except Exception as e:
        log.debug(f"  Flipkart fetch error: {e}")
    return None


def _fetch_amazon_image(driver, name: str) -> str | None:
    """Fallback: search Amazon India for the laptop, grab first product image."""
    from selenium.webdriver.common.by import By

    query = name.replace(" ", "+")
    url = f"https://www.amazon.in/s?k={query}"
    try:
        driver.get(url)
        time.sleep(random.uniform(2.5, 4.5))

        els = driver.find_elements(By.CSS_SELECTOR, "img.s-image")
        for el in els:
            src = el.get_attribute("src") or ""
            if src.startswith("https://") and "images-amazon" in src:
                return src
    except Exception as e:
        log.debug(f"  Amazon image fetch error: {e}")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_image(name: str, driver=None) -> str:
    """
    Return a real product image URL for the given laptop name.

    Priority:
      1. image_cache.json (instant)
      2. Flipkart search via Selenium
      3. Amazon India search via Selenium
      4. SVG placeholder (always works)

    Args:
        name:   Laptop name, e.g. "ASUS ROG Strix G15"
        driver: Optional existing Selenium driver (avoids re-launching)

    Returns:
        An image URL string (never None, never empty)
    """
    cache = _load_cache()
    if name in cache:
        return cache[name]

    own_driver = driver is None
    url = None

    try:
        if own_driver:
            try:
                driver = _build_driver()
            except Exception as e:
                log.warning(f"Could not launch Selenium: {e}")
                url = _placeholder_svg(name)
                cache[name] = url
                _save_cache(cache)
                return url

        url = _fetch_flipkart_image(driver, name)
        if not url:
            url = _fetch_amazon_image(driver, name)

    except Exception as e:
        log.warning(f"Image fetch failed for '{name}': {e}")
    finally:
        if own_driver and driver:
            try:
                driver.quit()
            except Exception:
                pass

    if not url:
        url = _placeholder_svg(name)

    cache[name] = url
    _save_cache(cache)
    log.info(f"  → {url[:80]}…" if len(url) > 80 else f"  → {url}")
    return url


# ── Prewarm catalogue ─────────────────────────────────────────────────────────

# All 22 models in mock_data.py catalogue — pre-warm images for these
_MOCK_CATALOGUE = [
    "ASUS VivoBook 15", "ASUS ROG Strix G15", "ASUS ZenBook 14",
    "HP Pavilion 15", "HP Omen 16", "HP Spectre x360",
    "Dell Inspiron 15", "Dell XPS 15", "Dell Alienware m15",
    "Lenovo IdeaPad Slim 3", "Lenovo ThinkPad E15", "Lenovo Legion 5",
    "Lenovo Yoga 9i", "Acer Aspire 7", "Acer Predator Helios 300",
    "Acer Swift 3", "MSI Modern 15", "MSI GF63 Thin",
    "Apple MacBook Air M2", "Apple MacBook Pro 14",
    "Samsung Galaxy Book3", "Mi RedmiBook Pro 15",
]


def prewarm():
    """Fetch and cache images for all mock catalogue models."""
    cache = _load_cache()
    todo = [n for n in _MOCK_CATALOGUE if n not in cache]
    if not todo:
        print(f"✅ All {len(_MOCK_CATALOGUE)} images already cached.")
        return

    print(f"Pre-warming {len(todo)} images (already cached: {len(_MOCK_CATALOGUE) - len(todo)}) …")
    try:
        driver = _build_driver()
    except Exception as e:
        print(f"❌ Could not launch Chrome: {e}")
        return

    try:
        for i, name in enumerate(todo, 1):
            print(f"  [{i}/{len(todo)}] {name}")
            url = get_image(name, driver=driver)
            is_real = url.startswith("https://")
            status = "✓ real" if is_real else "⚠ placeholder"
            print(f"       {status}")
            time.sleep(random.uniform(1.5, 3.5))
    finally:
        driver.quit()

    print(f"\n✅ Done! Cache: {_CACHE_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

    parser = argparse.ArgumentParser(description="Fetch / pre-warm laptop images")
    parser.add_argument("--prewarm", action="store_true", help="Pre-warm all mock catalogue images")
    parser.add_argument("--name", type=str, help="Fetch image for a single laptop name")
    args = parser.parse_args()

    if args.prewarm:
        prewarm()
    elif args.name:
        url = get_image(args.name)
        print(f"URL: {url}")
    else:
        parser.print_help()
