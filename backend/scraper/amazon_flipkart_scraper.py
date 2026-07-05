"""
scraper/amazon_flipkart_scraper.py  — v3 (fixed)
=================================================
Fixes vs v2:
  1. Specs parsed from PRODUCT TITLE (where Amazon actually puts them in search cards)
  2. Image URL: checks for 'm.media-amazon.com' (Amazon India CDN, not 'images-amazon')
  3. Flipkart skipped gracefully (their anti-bot blocks headless Chrome reliably)
  4. Default 15 pages × 10 queries = 1500+ unique Amazon listings

Usage:
    python scraper/amazon_flipkart_scraper.py               # 15 pages/query
    python scraper/amazon_flipkart_scraper.py --pages 20    # ~2000+ rows
    python scraper/amazon_flipkart_scraper.py --visible     # debug
"""

import argparse, csv, hashlib, logging, random, re, sys, time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    sys.exit("pip install selenium webdriver-manager beautifulsoup4")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("scraper")

ROOT    = Path(__file__).parent.parent
OUT_CSV = ROOT / "data" / "raw" / "data_real.csv"

CSV_COLS = [
    "name", "brand", "price",
    "processor", "Ram", "Ram_type", "ROM", "ROM_type",
    "GPU", "OS", "display_size", "resolution_width", "resolution_height",
    "warranty", "image_url", "buy_url", "source",
]

# ── 10 diverse queries for variety ───────────────────────────────────────────
AMAZON_QUERIES = [
    "laptop",
    "gaming laptop",
    "office laptop",
    "intel i5 laptop",
    "intel i7 laptop",
    "amd ryzen 5 laptop",
    "amd ryzen 7 laptop",
    "nvidia rtx laptop",
    "thin light laptop",
    "budget laptop",
    # --- Targeted Gap Fillers ---
    "intel core ultra 9 laptop",
    "intel core ultra 7 laptop",
    "intel core ultra 5 laptop",
    "intel core i9 laptop",
    "intel core i3 laptop",
    "amd ryzen 9 laptop",
    "amd ryzen 3 laptop",
    "apple macbook",
    "macbook pro m3",
    "macbook air m2",
    "macbook pro m2",
    "macbook m1",
    "workstation laptop",
    "creator laptop",
    "developer laptop",
    "student laptop",
    "32gb ram laptop",
    "64gb ram laptop",
    "16gb ram laptop",
    "budget laptop under 30000",
    "budget laptop under 40000",
    "premium laptop",
    "touchscreen laptop",
    "2-in-1 laptop",
    "oled laptop",
    "asus zenbook",
    "dell xps",
    "hp spectre",
    "lenovo thinkpad",
    "asus proart",
    "asus vivobook",
    "hp pavilion",
    "acer swift",
    "msi prestige",
]

# ─────────────────────────────────────────────────────────────────────────────
# SPEC PARSER — runs on the PRODUCT TITLE string
# Amazon search cards don't have spec bullets; all info is in the title.
# ─────────────────────────────────────────────────────────────────────────────

def _parse_specs_from_title(title: str) -> dict:
    t = title.lower()

    # ── Processor ────────────────────────────────────────────────────────────
    proc_patterns = [
        r"intel\s+core\s+ultra\s*\d+\w*",
        r"core\s+ultra\s*\d+\w*",
        r"intel core\s*i[3579][-\s]\d+\w*",
        r"intel core\s*i[3579]\s+\d+\w*",   # "i5 13420H"
        r"amd ryzen\s*[3579]\s*\d+\w*",
        r"apple m[123]\s*(?:pro|max|ultra)?",
        r"intel\s+celeron\s*\w*",
        r"intel\s+pentium\s*\w*",
        r"snapdragon\s*x\s*\w*",
        r"intel n\d+\w*",
        r"amd athlon\s*\w*",
    ]
    processor = "Intel Core i5"
    for pat in proc_patterns:
        m = re.search(pat, t)
        if m:
            processor = m.group(0).strip().title()
            break

    # ── RAM ──────────────────────────────────────────────────────────────────
    ram = 8.0
    ram_m = re.search(r"(\d+)\s*gb\s*(ddr5|ddr4|lpddr5x|lpddr5|lpddr4x|lpddr4)", t)
    if not ram_m:
        ram_m = re.search(r"(\d+)\s*gb\s*ram", t)
    if ram_m:
        ram = float(ram_m.group(1))

    rtype_m = re.search(r"(lpddr5x|lpddr5|lpddr4x|lpddr4|ddr5|ddr4)", t)
    ram_type = rtype_m.group(1).upper() if rtype_m else "DDR4"

    # ── Storage ──────────────────────────────────────────────────────────────
    rom = 512.0
    rom_m = re.search(r"(\d+)\s*(tb|gb)\s*(nvme|ssd|hdd|emmc)?", t)
    if rom_m:
        val = float(rom_m.group(1))
        # Skip RAM-sized matches (e.g. "16gb") — storage is usually ≥ 128 or is TB
        if rom_m.group(2) == "tb":
            rom = val * 1024
        elif val >= 128:
            rom = val
        else:
            # try again after the RAM match
            rom_m2 = re.search(r"(\d{3,4})\s*gb\s*(nvme|ssd|hdd)?", t)
            if rom_m2:
                rom = float(rom_m2.group(1))

    rom_type = "SSD" if any(k in t for k in ["ssd", "nvme", "nand"]) else (
               "HDD" if "hdd" in t else "SSD")

    # ── GPU ──────────────────────────────────────────────────────────────────
    gpu_patterns = [
        r"nvidia geforce rtx \d+\w*",
        r"nvidia rtx \d+\w*",
        r"rtx \d+\w*",
        r"nvidia geforce gtx \d+\w*",
        r"nvidia gtx \d+\w*",
        r"nvidia mx\d+\w*",
        r"amd radeon rx\s*\d+\w*",
        r"amd radeon\s+\w+",
        r"intel arc \w+",
        r"intel iris xe",
        r"intel uhd graphics",
        r"apple m[123]",
    ]
    gpu = None
    for pat in gpu_patterns:
        m = re.search(pat, t)
        if m:
            gpu = m.group(0).strip().title()
            break
            
    if not gpu:
        # If it's explicitly a gaming laptop, defaulting to Iris Xe poisons the data with 3-Lakh "integrated" GPUs.
        # Fallback to RTX 4060 for gaming laptops, otherwise Iris Xe.
        gaming_keywords = ["gaming", "rog", "legion", "predator", "alienware", "omen", "tuf", "loq", "nitro", "victus", "ideapad gaming"]
        if any(kw in t for kw in gaming_keywords):
            gpu = "Nvidia Rtx 4060"
        else:
            gpu = "Intel Iris Xe"
            
    # Default integrated GPU logic based on CPU if no specific GPU mentioned
    if gpu == "Intel Iris Xe" or gpu == "Intel Uhd Graphics":
        if "amd" in t and "ryzen" in t:
            gpu = "AMD Radeon FHD"
        elif "apple" in t or re.search(r"\bm[123]\b", t):
            gpu = "Apple M-series GPU"

    # ── OS ───────────────────────────────────────────────────────────────────
    if "macos" in t or "mac os" in t:
        os_val = "macOS"
    elif "win11" in t or "windows 11" in t or "win 11" in t:
        os_val = "Windows 11"
    elif "win10" in t or "windows 10" in t:
        os_val = "Windows 10"
    elif "dos" in t or "without os" in t or "freedos" in t:
        os_val = "DOS"
    else:
        os_val = "Windows 11"

    # ── Display size ─────────────────────────────────────────────────────────
    # Patterns: 15.6", 15.6'', 15.6 inch, 14"/35.6cm
    disp_m = re.search(r'(\d{1,2}\.\d)\s*(?:\'\'|"|inch|cm/)', t) or \
             re.search(r'(\d{1,2}\.\d)\s*(?:inch)', t)
    if disp_m:
        display_size = float(disp_m.group(1))
        # Sanity check — must be a realistic laptop screen size
        if not (10 <= display_size <= 18):
            display_size = 15.6
    else:
        display_size = 15.6

    # ── Resolution ───────────────────────────────────────────────────────────
    if "4k" in t or "3840" in t:
        res_w, res_h = 3840, 2160
    elif "2.8k" in t or "2880" in t:
        res_w, res_h = 2880, 1800
    elif "2k" in t or "2560" in t or "wqhd" in t:
        res_w, res_h = 2560, 1600
    elif "fhd" in t or "1920" in t or "full hd" in t:
        res_w, res_h = 1920, 1080
    elif "hd" in t:
        res_w, res_h = 1366, 768
    else:
        res_w, res_h = 1920, 1080

    return {
        "processor": processor,
        "Ram": ram, "Ram_type": ram_type,
        "ROM": rom, "ROM_type": rom_type,
        "GPU": gpu, "OS": os_val,
        "display_size": display_size,
        "resolution_width": res_w, "resolution_height": res_h,
        "warranty": 1,
    }


def _brand_from_name(name: str) -> str:
    known = ["ASUS", "HP", "Dell", "Lenovo", "Acer", "MSI", "Apple",
             "Samsung", "Xiaomi", "Mi", "Realme", "Infinix", "LG", "Honor", "Avita"]
    upper = name.upper()
    for b in known:
        if b.upper() in upper:
            return b
    return name.split()[0].title()


def _parse_price(text: str) -> float | None:
    digits = re.sub(r"[^\d]", "", str(text))
    if digits:
        v = float(digits)
        if 5000 < v < 500000:
            return v
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Selenium driver
# ─────────────────────────────────────────────────────────────────────────────

def _build_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
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
    opts.add_argument("--window-size=1366,768")
    opts.add_argument("--lang=en-IN")
    import os
    driver_path = r"C:\Users\Asus\.wdm\drivers\chromedriver\win64\149.0.7827.155\chromedriver.exe"
    
    try:
        if os.path.exists(driver_path):
            service = Service(driver_path)
        else:
            service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=opts)
    except Exception as e:
        log.error(f"Failed to initialize driver: {e}")
        # Try raw installation if cached fails
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=opts)
        
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return driver


def _sleep(lo=2.0, hi=5.0):
    time.sleep(random.uniform(lo, hi))


# ─────────────────────────────────────────────────────────────────────────────
# Amazon India scraper
# ─────────────────────────────────────────────────────────────────────────────

_AMZ_BASE   = "https://www.amazon.in"
_AMZ_SEARCH = _AMZ_BASE + "/s?k={query}&page={page}"


def _parse_amazon_card(card_html: str) -> dict | None:
    soup = BeautifulSoup(card_html, "lxml")

    # Name / title
    name_el = soup.select_one("h2 a span, h2 span")
    if not name_el:
        return None
    name = name_el.get_text(strip=True)
    if len(name) < 12:
        return None

    # Price
    whole = soup.select_one("span.a-price-whole")
    price = _parse_price(whole.get_text() if whole else "")
    if not price:
        return None

    # ── IMAGE — Amazon India CDN is m.media-amazon.com ───────────────────────
    image_url = ""
    img_el = soup.select_one("img.s-image")
    if img_el:
        src = img_el.get("src", "") or img_el.get("data-src", "")
        # Amazon India: https://m.media-amazon.com/images/I/...
        # Upgrade to a larger size variant by replacing size suffix
        if src.startswith("https://") and "amazon" in src:
            image_url = re.sub(r"\._[A-Z0-9_,]+_\.", "._SL500_.", src)

    # Buy URL
    link_el = soup.select_one("h2 a")
    href    = link_el.get("href", "") if link_el else ""
    buy_url = urljoin(_AMZ_BASE, href) if href else ""

    # Parse specs from the TITLE (not bullets — search cards don't have them)
    specs = _parse_specs_from_title(name)

    return {
        "name":      name,
        "brand":     _brand_from_name(name),
        "price":     price,
        "image_url": image_url,
        "buy_url":   buy_url,
        "source":    "amazon",
        **specs,
    }


def scrape_amazon(headless: bool, pages: int, queries: list[str]) -> list[dict]:
    results = []
    seen    = set()
    driver = _build_driver(headless=headless)

    for query in queries:
        log.info(f"\n[Amazon] Query: '{query}' ({pages} pages)")
        for page in range(1, pages + 1):
            url = _AMZ_SEARCH.format(query=query.replace(" ", "+"), page=page)
            try:
                driver.get(url)
                _sleep(2.5, 5.0)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                    )
                )
                soup  = BeautifulSoup(driver.page_source, "lxml")
                cards = soup.select("div[data-component-type='s-search-result']")
                new   = 0
                page_results = []
                for card in cards:
                    parsed = _parse_amazon_card(str(card))
                    if parsed:
                        key = hashlib.md5(parsed["name"].lower().encode()).hexdigest()
                        if key not in seen:
                            seen.add(key)
                            page_results.append(parsed)
                            new += 1
                results.extend(page_results)
                
                if page_results:
                    total = save_csv(page_results, OUT_CSV)
                    log.info(f"  p{page}: +{new} new (Session total: {len(results)}, DB total: {total})")
                else:
                    log.info(f"  p{page}: 0 new")
            except Exception as e:
                log.warning(f"  p{page} failed: {e}")
                _sleep(3, 6)
                if "invalid session id" in str(e).lower() or "disconnected" in str(e).lower() or "target window already closed" in str(e).lower() or "not reachable" in str(e).lower() or "gethandleverifier" in str(e).lower() or "read timed out" in str(e).lower():
                    log.warning("Driver appears dead. Rebuilding driver...")
                    try: driver.quit()
                    except: pass
                    _sleep(5, 10)
                    driver = _build_driver(headless=headless)

    driver.quit()
    log.info(f"[Amazon] Done: {len(results)} unique listings added this session")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Flipkart scraper  (best-effort — headless often blocked)
# ─────────────────────────────────────────────────────────────────────────────

_FK_BASE   = "https://www.flipkart.com"
_FK_SEARCH = _FK_BASE + "/search?q={query}&page={page}"

FK_QUERIES = [
    "laptop",
    "gaming laptop",
    "i5 laptop",
    "ryzen 5 laptop",
    "ryzen 7 laptop",
    "core ultra 9 laptop",
    "core ultra 7 laptop",
    "core ultra 5 laptop",
    "core i9 laptop",
    "core i7 laptop",
    "core i3 laptop",
    "ryzen 9 laptop",
    "ryzen 3 laptop",
    "apple macbook",
    "macbook pro m3",
    "macbook air m2",
    "32gb ram laptop",
    "64gb ram laptop",
    "16gb ram laptop",
    "creator laptop",
    "student laptop",
    "office laptop",
    "budget laptop under 30000",
    "budget laptop under 40000",
    "thin and light laptop",
    "touchscreen laptop",
    "oled laptop",
    "asus zenbook",
    "dell xps",
    "hp spectre",
    "lenovo thinkpad",
    "asus proart",
]

def _parse_flipkart_card(card_html: str) -> dict | None:
    soup = BeautifulSoup(card_html, "lxml")

    # Try every known Flipkart name class, then fall back to any anchor text
    name_el = soup.select_one(
        "div.KzDlHZ, a.s1Q9rs, div.wjcEIp, a._2UzuFa, div._4rR01T, "
        "a.IRpwTa, div.syl9yP, div._2WkVRV, a[title]"
    )
    if not name_el:
        # Last resort: any <a> inside the card whose text looks like a product name
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True)
            if len(txt) > 20 and any(b in txt.lower() for b in ["laptop","book","vivobook","ideapad","envy","aspire","legion","rog"]):
                name_el = a
                break
    if not name_el:
        return None
    name = name_el.get_text(strip=True)
    if len(name) < 8:
        return None

    price_el = soup.select_one("div.Nx9bqj, div._30jeq3, div._1vC4OE")
    if not price_el:
        # try any element containing ₹
        for el in soup.find_all(string=re.compile(r"₹\d")):
            price_el = el.parent
            break
    price = _parse_price(price_el.get_text() if price_el else "")
    if not price:
        return None

    # Image
    image_url = ""
    for sel in ["img.DByuf4", "img._396cs4", "img._2r_T1I", "img[src*='rukminim']"]:
        img_el = soup.select_one(sel)
        if img_el:
            src = img_el.get("src", "") or img_el.get("data-src", "")
            if src.startswith("https://") and "rukminim" in src:
                image_url = re.sub(r"/\d+/\d+/", "/416/416/", src)
                break

    link_el = soup.select_one("a[href*='/p/']")
    href    = link_el.get("href", "") if link_el else ""
    buy_url = urljoin(_FK_BASE, href) if href else ""

    specs = _parse_specs_from_title(name)
    return {"name": name, "brand": _brand_from_name(name), "price": price,
            "image_url": image_url, "buy_url": buy_url, "source": "flipkart", **specs}


def scrape_flipkart(headless: bool, pages: int, queries: list[str]) -> list[dict]:
    results = []
    seen    = set()
    driver = _build_driver(headless=headless)
    
    log.info("[Flipkart] Testing headless access …")
    try:
        driver.get(_FK_BASE + "/search?q=laptop")
        _sleep(3, 5)
        cards_test = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
        if not cards_test:
            log.warning("[Flipkart] 0 cards found — blocked. Skipping.")
            driver.quit()
            return []
        log.info(f"[Flipkart] Access OK ({len(cards_test)} cards on test page)")
    except Exception as e:
        log.warning(f"[Flipkart] Access test failed: {e}. Skipping.")
        driver.quit()
        return []

    for qi, query in enumerate(queries):
        log.info(f"\n[Flipkart] Query: '{query}'")
        query_results = 0
        for page in range(1, pages + 1):
            url = _FK_SEARCH.format(query=query.replace(" ", "+"), page=page)
            try:
                driver.get(url)
                _sleep(2.5, 5.0)
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-id]"))
                )
                soup  = BeautifulSoup(driver.page_source, "lxml")
                cards = soup.select("div[data-id]")
                new   = 0
                page_results = []
                for card in cards:
                    parsed = _parse_flipkart_card(str(card))
                    if parsed:
                        key = hashlib.md5(parsed["name"].lower().encode()).hexdigest()
                        if key not in seen:
                            seen.add(key)
                            page_results.append(parsed)
                            new += 1
                query_results += new
                results.extend(page_results)
                
                if page_results:
                    total = save_csv(page_results, OUT_CSV)
                    log.info(f"  p{page}: +{new} new (Session total: {len(results)}, DB total: {total})")
                else:
                    log.info(f"  p{page}: 0 new")
            except Exception as e:
                log.warning(f"  p{page} failed: {e}")
                _sleep(3, 6)
                # If driver crashed completely (e.g. invalid session id), try to rebuild it
                if "invalid session id" in str(e).lower() or "disconnected" in str(e).lower() or "target window already closed" in str(e).lower() or "not reachable" in str(e).lower() or "gethandleverifier" in str(e).lower() or "read timed out" in str(e).lower():
                    log.warning("Driver appears dead. Rebuilding driver...")
                    try: driver.quit()
                    except: pass
                    _sleep(5, 10)
                    driver = _build_driver(headless=headless)

        # If first query returned nothing, Flipkart is blocking — abort
        if qi == 0 and query_results == 0:
            log.warning("[Flipkart] First query returned 0 — selectors broken or blocked. Skipping all Flipkart.")
            driver.quit()
            return results

    driver.quit()
    log.info(f"[Flipkart] Done: {len(results)} unique listings added this session")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CSV writer
# ─────────────────────────────────────────────────────────────────────────────

def save_csv(rows: list[dict], path: Path) -> int:
    from filelock import FileLock
    lock_path = str(path) + ".lock"
    
    with FileLock(lock_path, timeout=60):
        existing = {}
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    key = hashlib.md5(r["name"].lower().encode()).hexdigest()
                    existing[key] = r
        for row in rows:
            key = hashlib.md5(row["name"].lower().encode()).hexdigest()
            existing[key] = row
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLS)
            writer.writeheader()
            for row in existing.values():
                writer.writerow({col: row.get(col, "") for col in CSV_COLS})
        return len(existing)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages",   type=int, default=15,
                        help="Pages per query (default 15 → ~1500 Amazon rows)")
    parser.add_argument("--site",    choices=["both","amazon","flipkart"], default="both")
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()

    headless_mode = not args.visible
    log.info(f"Scraper start → {args.site}, {args.pages} pages/query, headless={headless_mode}")
    all_rows = []

    if args.site in ("both", "flipkart"):
        all_rows.extend(scrape_flipkart(headless=headless_mode, pages=args.pages, queries=FK_QUERIES))
        _sleep(5, 10)

    if args.site in ("both", "amazon"):
        all_rows.extend(scrape_amazon(headless=headless_mode, pages=args.pages, queries=AMAZON_QUERIES))

    if not all_rows:
        log.error("No data collected.")
        sys.exit(1)

    total        = save_csv(all_rows, OUT_CSV)
    with_images  = sum(1 for r in all_rows if r.get("image_url","").startswith("https://"))
    log.info(f"\n✅ Done! New={len(all_rows)}  Images={with_images}/{len(all_rows)}  CSV total={total}")
    log.info(f"   Output: {OUT_CSV}")

    # Show spec variety stats
    procs = set(r.get("processor","") for r in all_rows)
    gpus  = set(r.get("GPU","") for r in all_rows)
    rams  = set(r.get("Ram","") for r in all_rows)
    log.info(f"   Processors: {len(procs)} unique — {sorted(procs)[:5]} …")
    log.info(f"   GPUs:       {len(gpus)} unique — {sorted(gpus)[:5]} …")
    log.info(f"   RAM sizes:  {sorted(rams)}")


if __name__ == "__main__":
    main()
