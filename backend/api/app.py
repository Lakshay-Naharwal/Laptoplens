"""
app.py  —  Laptop Price Intelligence API
Flask backend serving the React frontend and all REST endpoints.

Endpoints:
  GET  /                    → serve React build (index.html)
  GET  /api/metadata        → form options + model stats
  POST /api/predict         → ML price prediction + confidence band
  POST /api/recommend       → mock/live laptop recommendations
"""

import os
import json
import pickle
import asyncio
import logging
from pathlib import Path

import pandas as pd
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from backend.scraper.cache import scrape_cache
from backend.scraper.mock_data import generate_mock_listings

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ─── App setup ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
REACT_BUILD = BASE_DIR.parent / "frontend" / "dist"   # React production build output

app = Flask(
    __name__,
    static_folder=str(REACT_BUILD),
    static_url_path="",
)
# Allow local Vite during development; production can override with CORS_ORIGINS.
cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://laptoplens.vercel.app",
    ).split(",")
    if origin.strip()
]
if cors_origins:
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

# ─── Load ML model + metadata ─────────────────────────────────────────────────
MODEL_PATH    = BASE_DIR / "ml" / "model" / "laptop_price_model.pkl"
METADATA_PATH = BASE_DIR / "ml" / "model" / "metadata.pkl"

try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(METADATA_PATH, "rb") as f:
        metadata = pickle.load(f)
    logger.info(f"Model loaded. MAE = ₹{metadata.get('mae', '?'):,}")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    model = None
    metadata = None

# ─── Load real scraped data for recommendation engine ─────────────────────────
REAL_DATA_PATH  = BASE_DIR / "data" / "raw" / "data_real.csv"
_real_laptops: list[dict] = []

try:
    if REAL_DATA_PATH.exists():
        df_real = pd.read_csv(REAL_DATA_PATH)
        for _, row in df_real.iterrows():
            entry = row.to_dict()
            if pd.notna(entry.get("price")) and float(entry["price"]) > 0:
                _real_laptops.append(entry)
        logger.info(f"Loaded {len(_real_laptops)} real scraped laptops for recommendations")
    else:
        logger.info("data_real.csv not found — using mock data for recommendations")
except Exception as e:
    logger.warning(f"Could not load data_real.csv: {e}")

# ─── Use-case → keyword mapping (for recommendation filtering) ────────────────
USE_CASE_KEYWORDS = {
    "Gaming":      ["gaming", "rog", "omen", "predator", "legion", "alienware", "rtx", "gtx"],
    "Office":      ["business", "thinkpad", "latitude", "elitebook", "vivobook", "slim"],
    "Design":      ["creator", "spectre", "zenbook", "xps", "macbook", "studio"],
    "Programming": ["developer", "thinkpad", "xps", "macbook", "zenbook", "spectre"],
    "General":     [],   # no filter — all laptops qualify
}


def _json_body() -> dict:
    """Read a JSON request body without raising Flask parsing errors."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _as_float(value, default: float, min_value: float | None = None, max_value: float | None = None) -> float:
    """Parse a float with optional bounds, falling back to a safe default."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _as_int(value, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    """Parse an int with optional bounds, falling back to a safe default."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _as_bool(value, default: bool = False) -> bool:
    """Parse common JSON/form boolean values."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


from backend.api.utils import get_cores, get_threads, get_cpu_brand, get_cpu_tier, get_cpu_gen, get_gpu_brand, get_gpu_vram
def _recommend_from_real_data(
    predicted_price: float,
    confidence_band: float,
    user_specs: dict,
    use_case: str,
    count: int = 12,
) -> list[dict]:
    """
    Pull laptop recommendations directly from data_real.csv.
    image_url and buy_url come from the scraper — guaranteed to match each laptop.
    Returns empty list if no real data is loaded.
    """
    import hashlib

    if not _real_laptops:
        return []

    use_case_kws = USE_CASE_KEYWORDS.get(use_case, [])

    candidates = []
    for row in _real_laptops:
        price = float(row.get("price", 0))
        if price <= 0:
            continue

        name  = str(row.get("name", ""))
        lower = name.lower()

        # Use-case keyword filter
        if use_case and use_case_kws and use_case != "General":
            if not any(kw in lower for kw in use_case_kws):
                continue

        # Match score calculation
        price_delta = abs(price - predicted_price)
        price_score = max(0, 40 - int(price_delta / 500))

        gpu_raw = str(row.get("GPU", ""))
        gpu_brand = get_gpu_brand(gpu_raw)
        gpu_vram = get_gpu_vram(gpu_raw)
        is_dedicated = gpu_vram > 0 or gpu_brand == 'NVIDIA'
        is_apple = gpu_brand == 'Apple'
        is_basic_integrated = not is_dedicated and not is_apple

        # Use case logic using engineered features
        if use_case == "Office" and is_dedicated:
            continue
        if use_case == "Gaming" and not is_dedicated:
            continue
        if use_case == "Design" and is_basic_integrated:
            continue
        
        cpu_raw = str(row.get("processor", ""))
        cpu_tier = get_cpu_tier(cpu_raw)
        is_entry_cpu = cpu_tier in ["Core i3", "Ryzen 3", "Celeron", "Pentium", "Athlon"]
        if use_case == "Programming" and is_entry_cpu:
            continue
        
        # Scoring based on user preferences
        gpu_pref = user_specs.get("gpu_type", "integrated").lower()
        if gpu_pref == "dedicated" and is_dedicated:
            gpu_score = 30
        elif gpu_pref == "integrated" and (is_basic_integrated or is_apple):
            gpu_score = 30
        else:
            gpu_score = 5

        ram_val   = float(row.get("Ram", 0))
        user_ram  = float(user_specs.get("ram", 0))
        ram_score = 20 if (user_ram and ram_val >= user_ram) else (10 if ram_val >= user_ram // 2 else 0)

        brand_score = 10 if user_specs.get("brand") == row.get("brand") else 0
        cpu_score   = 10 if user_specs.get("cpu_tier") == cpu_tier else 0

        match_score = min(price_score + gpu_score + ram_score + brand_score + cpu_score, 100)

        pid = hashlib.md5(name.lower().encode()).hexdigest()[:12]
        candidates.append({
            "product_id":  pid,
            "name":        name,
            "brand":       str(row.get("brand", "")),
            "cpu":         cpu_raw,
            "gpu":         gpu_raw,
            "ram":         f"{int(float(row.get('Ram', 8)))}GB {row.get('Ram_type','DDR4')}",
            "storage":     f"{int(float(row.get('ROM', 512)))}GB {row.get('ROM_type','SSD')}",
            "display":     f"{row.get('display_size', 15.6)}\" FHD",
            "price":       price,
            "seller":      str(row.get("source", "scraped")).title(),
            "source":      str(row.get("source", "scraped")),
            "buy_url":     str(row.get("buy_url", "") or ""),
            "image_url":   str(row.get("image_url", "") or ""),
            "in_band":     price_delta <= confidence_band,
            "price_delta": round(price - predicted_price, 2),
            "match_score": match_score,
            "use_cases":   [use_case] if use_case else [],
        })

    if not candidates:
        return []

    # Soft sort: in-range first, then by score desc, then by price proximity
    candidates.sort(key=lambda x: (not x["in_band"], -x["match_score"], abs(x["price_delta"])))
    return candidates[:count]


# ─── Helper: run async scraper from sync Flask context ────────────────────────
def run_async(coro):
    """Execute an async coroutine from a synchronous Flask route."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════════
#   API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/metadata")
def api_metadata():
    """Return form dropdown options and model performance stats."""
    if not metadata:
        return jsonify({"error": "Model not loaded. Run train_model.py first."}), 503

    return jsonify({
        "categorical_cols": metadata["categorical_cols"],
        "numerical_cols":   metadata["numerical_cols"],
        "categories":       metadata["categories"],
        "mae":              metadata.get("mae", 5000),
        "r2":               metadata.get("r2", 0),
        "price_min":        metadata.get("price_min", 15000),
        "price_max":        metadata.get("price_max", 300000),
        "price_mean":       metadata.get("price_mean", 60000),
        "feature_importance": metadata.get("feature_importance", {}),
        "training_data_source": metadata.get("training_data_source", "unknown"),
        "training_rows":     metadata.get("training_rows"),
        "use_cases":        list(USE_CASE_KEYWORDS.keys()),
    })


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """
    Predict laptop price from user specs.

    Body (JSON):
        All categorical and numerical feature values from the model metadata,
        plus optional:
          - confidence_band (int): user-set ±INR tolerance (default: model MAE)
          - use_case (str): selected use-case tag

    Response:
        {
          price:            float,   # predicted INR
          price_min:        float,   # price - band
          price_max:        float,   # price + band
          confidence_band:  float,   # actual band used
          mae:              float,   # model MAE for reference
          formatted:        str,     # "₹XX,XXX"
        }
    """
    if not model or not metadata:
        return jsonify({"error": "Model not available"}), 503

    try:
        data = _json_body()

        # ── Build feature dict ──────────────────────────────────────────────
        inputs = {}
        for col in metadata["categorical_cols"]:
            inputs[col] = str(data.get(col, ""))

        for col in metadata["numerical_cols"]:
            inputs[col] = _as_float(data.get(col), 0.0)

        input_df = pd.DataFrame([inputs])

        # ── Predict ─────────────────────────────────────────────────────────
        raw_pred = float(model.predict(input_df)[0])
        predicted = max(raw_pred, 0.0)

        # ── Confidence band ─────────────────────────────────────────────────
        model_mae = metadata.get("mae", 5000)
        # User may override the band; clamp between 1000 and 50000
        user_band = data.get("confidence_band")
        if user_band is not None:
            confidence_band = _as_float(user_band, model_mae, 1000.0, 50000.0)
        else:
            confidence_band = model_mae

        return jsonify({
            "price":           round(predicted, 2),
            "price_min":       round(max(predicted - confidence_band, 0), 2),
            "price_max":       round(predicted + confidence_band, 2),
            "confidence_band": confidence_band,
            "mae":             model_mae,
            "feature_importance": metadata.get("feature_importance", {}),
            "formatted":       f"₹{predicted:,.0f}",
            "formatted_range": f"₹{max(predicted-confidence_band,0):,.0f} – ₹{predicted+confidence_band:,.0f}",
        })

    except Exception as e:
        logger.exception("Prediction error")
        return jsonify({"error": str(e)}), 400


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    """
    Return laptop recommendations matching user specs and predicted price band.

    Body (JSON):
        predicted_price:  float
        confidence_band:  float
        use_case:         str   (optional filter tag)
        ram:              float (for match scoring)
        gpu_type:         str   "integrated" | "dedicated"
        use_live:         bool  (default: false) — set true to trigger Playwright

    Response:
        { laptops: [...], source: "mock"|"live", cached: bool }
    """
    try:
        data = _json_body()
        predicted_price  = _as_float(data.get("predicted_price"), 50000.0, 0.0)
        confidence_band  = _as_float(data.get("confidence_band"), 10000.0, 1000.0, 50000.0)
        use_case         = data.get("use_case", "")
        use_live         = _as_bool(data.get("use_live"), False)

        processor_val = data.get("processor", "")
        gpu_val = data.get("GPU", "")

        user_specs = {
            "use_case":   use_case,
            "ram":        _as_float(data.get("Ram"), 0.0, 0.0),
            "gpu_type":   "dedicated" if get_gpu_vram(gpu_val) > 0 or get_gpu_brand(gpu_val) == "NVIDIA" else "integrated",
            "cpu_tier":   get_cpu_tier(processor_val),
            "cpu_brand":  get_cpu_brand(processor_val),
            "brand":      data.get("brand", ""),
        }

        # ── Cache key ───────────────────────────────────────────────────────
        cache_key = f"recommend::{int(predicted_price)}::{int(confidence_band)}::{use_case}"
        cached    = scrape_cache.get(cache_key)
        if cached:
            return jsonify({**cached, "cached": True})

        # ── Live scraper (optional) ──────────────────────────────────────────
        laptops = []
        source  = "mock"

        if use_live:
            try:
                from backend.scraper.flipkart_scraper import scrape_flipkart
                query   = _build_search_query(user_specs, use_case)
                laptops = run_async(scrape_flipkart(
                    query,
                    max_results=12,
                    predicted_price=predicted_price,
                    confidence_band=confidence_band,
                ))
                source = "live"
            except Exception as e:
                logger.warning(f"Live scraper failed, falling back to mock: {e}")

        # ── Real scraped data (primary source) ──────────────────────────────
        if not laptops and _real_laptops:
            laptops = _recommend_from_real_data(
                predicted_price=predicted_price,
                confidence_band=confidence_band,
                user_specs=user_specs,
                use_case=use_case,
                count=12,
            )
            if laptops:
                source = "real"

        # ── Mock fallback (when no real data available) ──────────────────────
        if not laptops:
            laptops = generate_mock_listings(
                predicted_price=predicted_price,
                confidence_band=confidence_band,
                user_specs=user_specs,
                count=12,
            )
            source = "mock"


        # ── Soft-sort: closest to predicted price first; in-band laptops float up ────────
        for laptop in laptops:
            laptop["price_delta"] = round(laptop["price"] - predicted_price, 2)
            laptop["in_band"]     = abs(laptop["price"] - predicted_price) <= confidence_band
        laptops.sort(key=lambda x: (not x["in_band"], abs(x["price_delta"])))

        in_band_count = sum(1 for l in laptops if l["in_band"])
        result = {
            "laptops":       laptops,
            "source":        source,
            "in_band_count": in_band_count,
            "total_count":   len(laptops),
        }
        # Cache for 3 hours
        scrape_cache.set(cache_key, result)

        return jsonify({**result, "cached": False})

    except Exception as e:
        logger.exception("Recommendation error")
        return jsonify({"error": str(e)}), 400


@app.route("/api/laptop-image")
def api_laptop_image():
    """
    Lazy image loader. Returns a real product image URL for a given laptop name.
    Results are cached in scraper/image_cache.json so Selenium only runs once.

    Query params:
        name: str   Laptop name, e.g. "ASUS ROG Strix G15"
    """
    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        from backend.scraper.image_fetcher import get_image
        url = get_image(name)
        return jsonify({"image_url": url, "name": name})
    except Exception as e:
        logger.warning(f"Image fetch failed for '{name}': {e}")
        return jsonify({"image_url": "", "name": name})


# ─── Serve React SPA ──────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """
    Serve the React build for all non-API routes.
    Falls back to index.html for client-side routing.
    """
    if REACT_BUILD.exists():
        target = REACT_BUILD / path
        if path and target.exists():
            return send_from_directory(str(REACT_BUILD), path)
        return send_from_directory(str(REACT_BUILD), "index.html")
    # Dev mode: no build yet
    return jsonify({"message": "React build not found. Run: cd frontend && npm run build"}), 404


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_search_query(user_specs: dict, use_case: str) -> str:
    """Build a Flipkart search query string from user specs."""
    parts = ["laptop"]
    ram = user_specs.get("ram")
    if ram:
        parts.append(f"{int(ram)}GB RAM")
    gpu_type = user_specs.get("gpu_type", "")
    if gpu_type == "dedicated":
        parts.append("dedicated graphics")
    if use_case in ("Gaming",):
        parts.append("gaming")
    if user_specs.get("brand"):
        parts.append(user_specs["brand"])
    return " ".join(parts)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
