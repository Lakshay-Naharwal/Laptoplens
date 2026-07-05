import requests
from bs4 import BeautifulSoup
import time
import sys
import hashlib
import logging
import random

sys.path.insert(0, 'd:/ML Projects/Laptoplens')
from backend.scraper.amazon_flipkart_scraper import _parse_specs_from_title, save_csv, OUT_CSV, _brand_from_name, _parse_price

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("smartprix_overnight")

def scrape_smartprix_overnight(pages=100):
    seen = set()
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ]
    
    log.info(f"Starting OVERNIGHT Smartprix scraper for {pages} pages...")
    
    page = 1
    while page <= pages:
        url = f"https://www.smartprix.com/laptops?page={page}"
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        try:
            log.info(f"Fetching page {page}...")
            res = requests.get(url, headers=headers, timeout=20)
            
            if res.status_code == 429 or res.status_code == 403:
                log.warning(f"Rate limited (Status {res.status_code}). Sleeping for 60 seconds...")
                time.sleep(60)
                continue # Retry same page
                
            if res.status_code != 200:
                log.warning(f"Page {page} returned status {res.status_code}. Skipping to next.")
                page += 1
                time.sleep(10)
                continue
                
            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.find_all("div", class_="sm-product")
            
            if not cards:
                log.warning(f"No cards found on page {page}. We might have reached the end of the catalog.")
                break
                
            page_results = []
            new = 0
            for card in cards:
                name_el = card.find("h2")
                price_el = card.find("span", class_="price")
                img_el = card.find("img")
                link_el = card.find("a", class_="name")
                
                if not name_el or not price_el:
                    continue
                    
                name = name_el.get_text(strip=True)
                price = _parse_price(price_el.get_text())
                if not price or len(name) < 10:
                    continue
                    
                image_url = img_el.get("src", "") if img_el else ""
                buy_url = "https://www.smartprix.com" + link_el.get("href", "") if link_el else ""
                
                specs = _parse_specs_from_title(name)
                
                parsed = {
                    "name": name,
                    "brand": _brand_from_name(name),
                    "price": price,
                    "image_url": image_url,
                    "buy_url": buy_url,
                    "source": "smartprix",
                    **specs
                }
                
                key = hashlib.md5(parsed["name"].lower().encode()).hexdigest()
                if key not in seen:
                    seen.add(key)
                    page_results.append(parsed)
                    new += 1
                    
            if page_results:
                # Save incrementally per page so we don't lose data on crash
                total = save_csv(page_results, OUT_CSV)
                log.info(f"Page {page}: +{new} new (Total CSV rows: {total})")
            else:
                log.info(f"Page {page}: 0 new (Already in DB)")
                
            page += 1
            
            # Sleep aggressively to prevent timeouts/blocks overnight
            sleep_time = random.uniform(15.0, 30.0)
            log.info(f"Sleeping for {sleep_time:.1f}s to avoid bot detection...")
            time.sleep(sleep_time)
            
        except requests.exceptions.Timeout:
            log.warning(f"Timeout on page {page}. Sleeping for 60s and retrying...")
            time.sleep(60)
        except Exception as e:
            log.error(f"Error on page {page}: {e}. Skipping to next.")
            page += 1
            time.sleep(15)

if __name__ == "__main__":
    scrape_smartprix_overnight(pages=80)
