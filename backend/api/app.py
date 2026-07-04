"""
app.py  —  Laptop Price Intelligence API
Flask backend serving the React frontend and all REST endpoints.

Endpoints:
  GET  /                    → serve React build (index.html)
  GET  /api/metadata        → form options + model stats
  POST /api/predict         → ML price prediction + confidence band
  POST /api/recommend       → cosine-similarity + price-band laptop recommendations
  GET  /api/laptop-image    → lazy image fetcher (Selenium, cached)
"""

import os
import pickle
import asyncio
import logging
from pathlib import Path

import numpy as np
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



def _as_bool(value, default: bool = False) -> bool:
    """Parse common JSON/form boolean values."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


from backend.api.utils import get_cpu_brand, get_cpu_tier, get_gpu_brand, get_gpu_vram

# ─── Spec normalisation constants (used for cosine similarity) ────────────────
# Upper bounds for each continuous feature — used to scale values to [0, 1].
_NORM = {
    "ram":     128.0,
    "rom":     8192.0,
    "display": 18.0,
    "res_w":   3840.0,
    "res_h":   2160.0,
    "warranty": 5.0,
}

# CPU tier → ordinal score (higher = more powerful)
_CPU_TIER_SCORE = {
    "Core i9": 1.0, "Core ultra 9": 1.0,
    "Core i7": 0.8, "Core ultra 7": 0.85,
    "Core i5": 0.6, "Core ultra 5": 0.65,
    "Ryzen 9": 1.0, "Ryzen 7": 0.8, "Ryzen 5": 0.6,
    "M3": 0.95, "M2": 0.85, "M1": 0.75,
    "Core i3": 0.35, "Ryzen 3": 0.35,
    "Celeron": 0.15, "Pentium": 0.15, "Athlon": 0.15,
    "Other": 0.3,
}


def _build_spec_vector(ram: float, rom: float, display: float, res_w: float,
                       res_h: float, warranty: float, cpu_tier: str,
                       is_dedicated: bool, is_apple: bool) -> np.ndarray:
    """
    Build a normalised spec feature vector for cosine-similarity computation.

    Dimensions (9):
      0 – RAM (normalised to 128 GB max)
      1 – ROM / storage (normalised to 8192 GB max)
      2 – display size (normalised to 18" max)
      3 – resolution width (normalised to 3840 max)
      4 – resolution height (normalised to 2160 max)
      5 – warranty (normalised to 5 years max)
      6 – CPU tier ordinal score (0–1)
      7 – dedicated GPU flag (0 or 1)
      8 – Apple Silicon GPU flag (0 or 1)
    """
    return np.array([
        min(ram,     _NORM["ram"])     / _NORM["ram"],
        min(rom,     _NORM["rom"])     / _NORM["rom"],
        min(display, _NORM["display"]) / _NORM["display"],
        min(res_w,   _NORM["res_w"])   / _NORM["res_w"],
        min(res_h,   _NORM["res_h"])   / _NORM["res_h"],
        min(warranty,_NORM["warranty"])/ _NORM["warranty"],
        _CPU_TIER_SCORE.get(cpu_tier, 0.3),
        1.0 if is_dedicated else 0.0,
        1.0 if is_apple else 0.0,
    ], dtype=float)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity in [0, 1] between two non-zero vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0.0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


def _recommend_from_real_data(
    predicted_price: float,
    confidence_band: float,
    user_specs: dict,
    use_case: str,
    count: int = 12,
) -> list[dict]:
    """
    Pull laptop recommendations from data_real.csv using a hybrid scoring approach:

    1. Hard filters  — use-case-specific GPU/CPU constraints applied first.
    2. Cosine similarity — spec vector (RAM, ROM, display, resolution, warranty,
       CPU tier, GPU type) normalised to [0,1] and compared against the user query
       vector via cosine similarity.
    3. Price proximity — absolute distance from the predicted price, scaled 0–1.
    4. Final match_score = round((cosine_sim * 0.70 + price_score * 0.30) * 100).

    image_url and buy_url come from the scraper CSV — no extra network calls needed.
    Returns an empty list if no real data is loaded.
    """
    import hashlib

    if not _real_laptops:
        return []

    use_case_kws = USE_CASE_KEYWORDS.get(use_case, [])

    # ── Build the user query spec vector ────────────────────────────────────
    user_ram      = float(user_specs.get("ram", 8.0))
    gpu_pref      = user_specs.get("gpu_type", "integrated").lower()
    user_cpu_tier = user_specs.get("cpu_tier", "Other")
    user_is_dedicated = gpu_pref == "dedicated"
    user_is_apple     = user_cpu_tier in ("M1", "M2", "M3")

    # For continuous fields not directly in user_specs, use sensible defaults
    # (the user's form provides Ram; the rest we infer from use-case context)
    user_rom     = 512.0 if use_case not in ("Gaming", "Design") else 1024.0
    user_display = 15.6
    user_res_w   = 1920.0
    user_res_h   = 1080.0
    user_warranty= 1.0

    query_vec = _build_spec_vector(
        ram=user_ram, rom=user_rom, display=user_display,
        res_w=user_res_w, res_h=user_res_h, warranty=user_warranty,
        cpu_tier=user_cpu_tier,
        is_dedicated=user_is_dedicated,
        is_apple=user_is_apple,
    )

    # Max price delta across the dataset — used to normalise price proximity
    max_price_delta = max(predicted_price * 2, confidence_band * 4, 1.0)

    candidates = []
    for row in _real_laptops:
        price = float(row.get("price", 0))
        if price <= 0:
            continue

        name  = str(row.get("name", ""))
        lower = name.lower()

        # ── Use-case keyword pre-filter ───────────────────────────────────
        if use_case and use_case_kws and use_case != "General":
            if not any(kw in lower for kw in use_case_kws):
                continue

        # ── Derived GPU / CPU features ────────────────────────────────────
        gpu_raw   = str(row.get("GPU", ""))
        gpu_brand = get_gpu_brand(gpu_raw)
        gpu_vram  = get_gpu_vram(gpu_raw)
        is_dedicated       = gpu_vram > 0 or gpu_brand == "NVIDIA"
        is_apple           = gpu_brand == "Apple"
        is_basic_integrated = not is_dedicated and not is_apple

        cpu_raw  = str(row.get("processor", ""))
        cpu_tier = get_cpu_tier(cpu_raw)
        is_entry_cpu = cpu_tier in ["Core i3", "Ryzen 3", "Celeron", "Pentium", "Athlon"]

        # ── Hard use-case filters (must-pass) ─────────────────────────────
        if use_case == "Office"      and is_dedicated:        continue
        if use_case == "Gaming"      and not is_dedicated:    continue
        if use_case == "Design"      and is_basic_integrated: continue
        if use_case == "Programming" and is_entry_cpu:        continue

        # ── Cosine similarity (spec match) ────────────────────────────────
        ram_val     = float(row.get("Ram", 8.0))
        rom_val     = float(row.get("ROM", 512.0))
        disp_val    = float(row.get("display_size", 15.6))
        res_w_val   = float(row.get("resolution_width", 1920.0))
        res_h_val   = float(row.get("resolution_height", 1080.0))
        warranty_val= float(row.get("warranty", 1.0))

        candidate_vec = _build_spec_vector(
            ram=ram_val, rom=rom_val, display=disp_val,
            res_w=res_w_val, res_h=res_h_val, warranty=warranty_val,
            cpu_tier=cpu_tier,
            is_dedicated=is_dedicated,
            is_apple=is_apple,
        )
        cosine_sim = _cosine_similarity(query_vec, candidate_vec)

        # ── Price proximity score (0–1, higher = closer to predicted) ─────
        price_delta   = price - predicted_price
        price_prox    = max(0.0, 1.0 - abs(price_delta) / max_price_delta)

        # ── Hybrid match score (cosine 70% + price proximity 30%) ─────────
        match_score = round((cosine_sim * 0.70 + price_prox * 0.30) * 100)

        pid = hashlib.md5(name.lower().encode()).hexdigest()[:12]
        candidates.append({
            "product_id":  pid,
            "name":        name,
            "brand":       str(row.get("brand", "")),
            "cpu":         cpu_raw,
            "gpu":         gpu_raw,
            "ram":         f"{int(ram_val)}GB {row.get('Ram_type', 'DDR4')}",
            "storage":     f"{int(rom_val)}GB {row.get('ROM_type', 'SSD')}",
            "display":     f"{disp_val}\" {int(res_w_val)}×{int(res_h_val)}",
            "price":       price,
            "seller":      str(row.get("source", "scraped")).title(),
            "source":      str(row.get("source", "scraped")),
            "buy_url":     str(row.get("buy_url", "") or ""),
            "image_url":   str(row.get("image_url", "") or ""),
            "in_band":     abs(price_delta) <= confidence_band,
            "price_delta": round(price_delta, 2),
            "match_score": match_score,
            "use_cases":   [use_case] if use_case else [],
        })

    if not candidates:
        return []

    # Soft sort: in-range first, then by cosine-based match_score desc, then price proximity
    candidates.sort(key=lambda x: (not x["in_band"], -x["match_score"], abs(x["price_delta"])))
    return candidates[:count]


# ─── Helper: run async scraper from sync Flask context ────────────────────────
def run_async(coro):
    """Execute an async coroutine from a synchronous Flask route."""
    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
        # Safe bounds for numerical features to prevent garbage predictions
        NUM_BOUNDS = {
            "Ram": (1.0, 128.0),
            "ROM": (32.0, 8192.0),
            "display_size": (10.0, 18.0),
            "resolution_width": (800.0, 7680.0),
            "resolution_height": (600.0, 4320.0),
            "warranty": (0.0, 5.0),
        }
        inputs = {}
        for col in metadata["categorical_cols"]:
            val = data.get(col, "")
            # Reject completely empty categorical values
            if val is None or str(val).strip() == "":
                return jsonify({"error": f"Missing required field: {col}"}), 400
            inputs[col] = str(val)

        for col in metadata["numerical_cols"]:
            lo, hi = NUM_BOUNDS.get(col, (0.0, float("inf")))
            inputs[col] = _as_float(data.get(col), lo, lo, hi)

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
                if laptops:
                    source = "live"
                else:
                    logger.info("Live scraper returned no results. Falling back.\n")
            except Exception as e:
                logger.warning(f"Live scraper failed, falling back to cached data: {e}")

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
            else:
                logger.info("No matching real data found. Falling back to mock data.\n")

        # ── Mock fallback (when no real data available) ──────────────────────
        if not laptops:
            laptops = generate_mock_listings(
                predicted_price=predicted_price,
                confidence_band=confidence_band,
                user_specs=user_specs,
                count=12,
            )
            source = "mock"  # Corrects source label when use_live=True but all scrapers/data failed
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
