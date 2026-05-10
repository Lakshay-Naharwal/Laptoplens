"""
scraper/mock_data.py
Generates realistic mock laptop listings for development and demo purposes.
Used when USE_MOCK=true env var is set or when the live scraper fails.

Mock listings are seeded from real brand/model patterns and priced within
a realistic band around the predicted price so match scores make sense.
"""

import hashlib
import random
import math
from datetime import datetime, timedelta
from typing import Optional


# ─── Laptop catalogue (brand, series, typical suffix patterns) ─────────────────
_CATALOGUE = [
    # (brand, series, processor_hint, gpu_hint, typical_use)
    ("ASUS", "VivoBook 15",       "Intel Core i5-1235U", "Intel Iris Xe",      ["Office", "General"]),
    ("ASUS", "ROG Strix G15",     "AMD Ryzen 7-6800H",   "NVIDIA RTX 3060",    ["Gaming"]),
    ("ASUS", "ZenBook 14",        "Intel Core i7-1260P", "Intel Iris Xe",      ["Programming", "Office"]),
    ("HP",   "Pavilion 15",       "Intel Core i5-1235U", "Intel UHD",          ["General", "Office"]),
    ("HP",   "Omen 16",           "Intel Core i7-12700H","NVIDIA RTX 3070 Ti", ["Gaming"]),
    ("HP",   "Spectre x360",      "Intel Core i7-1255U", "Intel Iris Xe",      ["Design", "Programming"]),
    ("Dell", "Inspiron 15",       "Intel Core i5-1235U", "NVIDIA MX550",       ["General", "Office"]),
    ("Dell", "XPS 15",            "Intel Core i7-12700H","NVIDIA RTX 3050 Ti", ["Design", "Programming"]),
    ("Dell", "Alienware m15",     "Intel Core i9-12900H","NVIDIA RTX 3080 Ti", ["Gaming"]),
    ("Lenovo","IdeaPad Slim 3",   "AMD Ryzen 5-5500U",   "AMD Radeon",         ["General", "Office"]),
    ("Lenovo","ThinkPad E15",     "Intel Core i5-1235U", "Intel Iris Xe",      ["Programming", "Office"]),
    ("Lenovo","Legion 5",         "AMD Ryzen 7-6800H",   "NVIDIA RTX 3060",    ["Gaming"]),
    ("Lenovo","Yoga 9i",          "Intel Core i7-1260P", "Intel Iris Xe",      ["Design", "Programming"]),
    ("Acer", "Aspire 7",          "AMD Ryzen 5-5500U",   "NVIDIA GTX 1650",    ["General", "Gaming"]),
    ("Acer", "Predator Helios 300","Intel Core i7-12700H","NVIDIA RTX 3070",   ["Gaming"]),
    ("Acer", "Swift 3",           "Intel Core i5-1235U", "Intel Iris Xe",      ["Office", "General"]),
    ("MSI",  "Modern 15",         "Intel Core i5-1235U", "Intel Iris Xe",      ["Office"]),
    ("MSI",  "GF63 Thin",         "Intel Core i5-12500H","NVIDIA RTX 3050",    ["Gaming"]),
    ("Apple","MacBook Air M2",    "Apple M2",            "Apple M2 GPU",        ["Design", "Programming"]),
    ("Apple","MacBook Pro 14",    "Apple M2 Pro",        "Apple M2 Pro GPU",    ["Design", "Programming"]),
    ("Samsung","Galaxy Book3",    "Intel Core i7-1360P", "Intel Iris Xe",      ["Office", "General"]),
    ("Mi",   "RedmiBook Pro 15",  "Intel Core i5-12450H","NVIDIA MX550",       ["General", "Office"]),
]

_SELLERS = ["Flipkart", "Amazon", "Croma", "Reliance Digital", "Vijay Sales"]
_STORAGE_OPTS = ["256GB SSD", "512GB SSD", "512GB SSD + 1TB HDD", "1TB SSD", "1TB HDD + 256GB SSD"]
_RAM_OPTS = ["8GB DDR4", "8GB DDR5", "16GB DDR4", "16GB DDR5", "32GB DDR5"]
_DISPLAY_OPTS = [
    ("13.3", "FHD (1920×1080)"),
    ("14.0", "FHD (1920×1080)"),
    ("15.6", "FHD (1920×1080)"),
    ("15.6", "QHD (2560×1440)"),
    ("16.0", "QHD (2560×1440)"),
    ("17.3", "FHD (1920×1080)"),
]


def _product_id(name: str, source: str) -> str:
    """Generate a stable, short product ID from name + source."""
    raw = f"{name.lower()}::{source.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _match_score(laptop: dict, user_specs: dict) -> int:
    """
    Compute a 0–100 match score between a mock laptop and user specs.
    Weights: use_case (30) + gpu_type (25) + price_band (25) + ram (20).
    """
    score = 0

    # Use-case match (30 pts)
    use_case = user_specs.get("use_case", "")
    if use_case and use_case in laptop.get("use_cases", []):
        score += 30
    elif use_case:
        score += 10  # partial credit for any laptop

    # GPU type match (25 pts)
    gpu_pref = user_specs.get("gpu_type", "integrated").lower()
    laptop_gpu = laptop.get("gpu", "").lower()
    if gpu_pref == "dedicated" and any(k in laptop_gpu for k in ["rtx", "gtx", "rx", "mx"]):
        score += 25
    elif gpu_pref == "integrated" and any(k in laptop_gpu for k in ["intel", "amd radeon", "m2"]):
        score += 25
    else:
        score += 10

    # Price within user's band (25 pts)
    predicted    = user_specs.get("predicted_price", 0)
    band         = user_specs.get("confidence_band", 10000)
    laptop_price = laptop.get("price", 0)
    if predicted and abs(laptop_price - predicted) <= band:
        score += 25
    elif predicted and abs(laptop_price - predicted) <= band * 1.5:
        score += 12

    # RAM match (20 pts)
    user_ram = user_specs.get("ram", 0)
    laptop_ram_str = laptop.get("ram", "8GB")
    laptop_ram = int("".join(filter(str.isdigit, laptop_ram_str.split()[0])) or 0)
    if user_ram and laptop_ram >= user_ram:
        score += 20
    elif user_ram and laptop_ram >= user_ram // 2:
        score += 10

    return min(score, 100)


def generate_mock_listings(
    predicted_price: float,
    confidence_band: float,
    user_specs: Optional[dict] = None,
    count: int = 12,
    seed: Optional[int] = None,
) -> list[dict]:
    """
    Generate `count` mock laptop listings priced around `predicted_price ± band`.
    Listings are seeded so the same prediction always returns the same mocks.

    Args:
        predicted_price:  ML model prediction in INR
        confidence_band:  ± INR tolerance (user-set or from MAE)
        user_specs:       dict with use_case, ram, gpu_type, etc.
        count:            number of listings to generate
        seed:             RNG seed (defaults to hash of predicted_price)

    Returns:
        List of dicts matching the recommendation card schema.
    """
    if seed is None:
        seed = int(predicted_price) % 9999
    rng = random.Random(seed)
    user_specs = user_specs or {}

    listings = []
    shuffled_catalogue = _CATALOGUE[:]
    rng.shuffle(shuffled_catalogue)

    # Price spread: 70% within band, 30% just outside (realistic market noise)
    for i, (brand, series, cpu, gpu, use_cases) in enumerate(shuffled_catalogue[:count]):
        # Price within ±band (or ±1.5×band for the outliers)
        spread = confidence_band if i < int(count * 0.7) else confidence_band * 1.5
        price = rng.uniform(
            max(predicted_price - spread, 15000),
            predicted_price + spread,
        )
        price = round(price / 100) * 100  # round to nearest ₹100

        ram_str   = rng.choice(_RAM_OPTS)
        storage   = rng.choice(_STORAGE_OPTS)
        display_sz, resolution = rng.choice(_DISPLAY_OPTS)
        seller    = rng.choice(_SELLERS)
        variant   = rng.choice(["", " (2023)", " Gen 12", " Pro"])

        name = f"{brand} {series}{variant}"
        product_id = _product_id(name, seller)

        # Check image cache only (non-blocking). If not cached, RecommendationCard
        # will fetch it lazily via /api/laptop-image without blocking page load.
        image_url = ""
        try:
            import json
            from pathlib import Path as _P
            _cache_path = _P(__file__).parent / "image_cache.json"
            if _cache_path.exists():
                _cache = json.loads(_cache_path.read_text(encoding="utf-8"))
                image_url = _cache.get(name, "")
        except Exception:
            pass

        laptop = {
            "product_id":  product_id,
            "name":        name,
            "brand":       brand,
            "cpu":         cpu,
            "gpu":         gpu,
            "ram":         ram_str,
            "storage":     storage,
            "display":     f"{display_sz}\" {resolution}",
            "price":       price,
            "seller":      seller,
            "source":      "mock",
            "use_cases":   use_cases,
            "buy_url":     f"https://www.{seller.lower().replace(' ', '')}.com/laptop/{product_id}",
            "image_url":   image_url,
            "in_band":     abs(price - predicted_price) <= confidence_band,
        }


        # Compute match score
        laptop["match_score"] = _match_score(
            laptop,
            {**user_specs, "predicted_price": predicted_price, "confidence_band": confidence_band},
        )

        listings.append(laptop)

    # Sort: best match first, then by price proximity
    listings.sort(
        key=lambda x: (-x["match_score"], abs(x["price"] - predicted_price))
    )
    return listings


def generate_mock_price_history(
    product_id: str,
    current_price: float,
    days: int = 365,
) -> list[dict]:
    """
    Generate a realistic price history for a product (simulates price drops,
    sales events, and gradual inflation) for the last `days` days.

    Returns list of {price, scraped_at} dicts ordered oldest → newest.
    """
    rng = random.Random(product_id)
    history = []
    now = datetime.now()

    # Start price (slightly higher — products tend to drop over time)
    start_price = current_price * rng.uniform(1.05, 1.25)
    price = start_price

    for day_offset in range(days, -1, -1):
        date = now - timedelta(days=day_offset)

        # Simulate sale events (Diwali ~Oct, Republic Day ~Jan, Big Billion Day ~Oct)
        month = date.month
        is_sale = month in (1, 7, 10, 11) and rng.random() < 0.08
        if is_sale:
            price *= rng.uniform(0.85, 0.94)  # 6–15% sale drop

        # Daily drift: slight downward trend + noise
        drift = rng.gauss(-0.03, 0.5)  # %
        price = price * (1 + drift / 100)
        price = max(price, current_price * 0.7)  # floor: 70% of current

        # Only record every few days to keep data realistic
        if day_offset % rng.randint(2, 4) == 0:
            history.append({
                "price":      round(price / 100) * 100,
                "scraped_at": date.strftime("%Y-%m-%d %H:%M:%S"),
            })

    # Ensure the last entry matches the current price
    history.append({
        "price":      round(current_price / 100) * 100,
        "scraped_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return history
