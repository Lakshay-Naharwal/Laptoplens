import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.pipeline import Pipeline
import pickle
import os
import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Paths ────────────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(script_dir, "model")
os.makedirs(model_dir, exist_ok=True)

# ─── 1. Load Data ─────────────────────────────────────────────────────────────
real_data_path = os.path.join(script_dir, "data_real.csv")
parser = argparse.ArgumentParser(description="Train the laptop price model")
parser.add_argument(
    "--data-source",
    choices=["clean", "real"],
    default=os.environ.get("TRAIN_DATA_SOURCE", "clean"),
    help="Use curated data.csv by default; pass 'real' only for scraper experiments.",
)
args = parser.parse_args()

# The scraped CSV is useful for recommendations, but its specs are parsed from
# marketplace titles and are too noisy to be the default training source.
clean_data_path = os.path.join(script_dir, "data.csv")
data_path = real_data_path if args.data_source == "real" else clean_data_path
if not os.path.exists(data_path):
    raise FileNotFoundError(f"Training data not found: {data_path}")
print(f"Training source: {args.data_source} ({data_path})")

df = pd.read_csv(data_path)

# ─── 2. Preprocessing ─────────────────────────────────────────────────────────
import re

def extract_number(val):
    """Pull the first numeric substring from a value (e.g. '8GB' → 8.0)."""
    try:
        digits = "".join(filter(lambda c: c.isdigit() or c == ".", str(val)))
        return float(digits) if digits else 0.0
    except Exception:
        return 0.0

def clean_rom(val):
    """Normalise storage to GB (TB values × 1024)."""
    val = str(val).upper()
    num = extract_number(val)
    return num * 1024 if "TB" in val else num

def get_cores(val):
    val = str(val).lower()
    if 'dual' in val: return 2
    if 'quad' in val: return 4
    if 'hexa' in val: return 6
    if 'octa' in val: return 8
    match = re.search(r'(\d+)\s*cores', val)
    return int(match.group(1)) if match else 4

def get_threads(val):
    match = re.search(r'(\d+)\s*threads', val)
    return int(match.group(1)) if match else 8

def get_cpu_brand(val):
    val = str(val).lower()
    if 'intel' in val: return 'Intel'
    if 'amd' in val: return 'AMD'
    if 'apple' in val: return 'Apple'
    return 'Other'

def get_cpu_tier(val):
    val = str(val).lower()
    for tier in ['i9', 'i7', 'i5', 'i3', 'ryzen 9', 'ryzen 7', 'ryzen 5', 'ryzen 3', 'm1', 'm2', 'm3', 'celeron', 'pentium', 'athlon']:
        if tier in val: return tier.upper()
    return 'Other'

def get_gpu_brand(val):
    val = str(val).lower()
    if any(k in val for k in ['nvidia', 'geforce', 'rtx', 'gtx']): return 'NVIDIA'
    if any(k in val for k in ['amd', 'radeon']): return 'AMD'
    if any(k in val for k in ['intel', 'iris', 'uhd']): return 'Intel'
    if any(k in val for k in ['apple', 'm1', 'm2', 'm3']): return 'Apple'
    return 'Other'

def get_gpu_vram(val):
    match = re.search(r'(\d+)gb', str(val).lower())
    return float(match.group(1)) if match else 0.0

# Initial cleaning
df["Ram"] = df["Ram"].apply(extract_number)
df["ROM"] = df["ROM"].apply(clean_rom)
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df = df.dropna(subset=["price"])
df = df[(df["price"] >= 10000) & (df["price"] <= 500000)]

# Feature Engineering
if 'CPU' in df.columns:
    df['cpu_cores'] = df['CPU'].apply(get_cores)
    df['cpu_threads'] = df['CPU'].apply(get_threads)
else:
    df['cpu_cores'] = 4
    df['cpu_threads'] = 8

df['cpu_brand'] = df['processor'].apply(get_cpu_brand)
df['cpu_tier'] = df['processor'].apply(get_cpu_tier)
df['gpu_brand'] = df['GPU'].apply(get_gpu_brand)
df['gpu_vram'] = df['GPU'].apply(get_gpu_vram)

# ─── 3. Features & Target ─────────────────────────────────────────────────────
categorical_cols = ["brand", "cpu_brand", "cpu_tier", "Ram_type", "ROM_type", "gpu_brand", "OS"]
numerical_cols = [
    "Ram",
    "ROM",
    "cpu_cores",
    "cpu_threads",
    "gpu_vram",
    "display_size",
    "resolution_width",
    "resolution_height",
    "warranty",
]

# Keep only columns that actually exist in the CSV
categorical_cols = [c for c in categorical_cols if c in df.columns]
numerical_cols = [c for c in numerical_cols if c in df.columns]

X = df[categorical_cols + numerical_cols]
y = df["price"]

# ─── 4. Preprocessing Pipeline ────────────────────────────────────────────────
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numerical_cols),
        (
            "cat",
            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            categorical_cols,
        ),
    ]
)

# ─── 5. Model Pipeline ────────────────────────────────────────────────────────
feature_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "regressor",
            xgb.XGBRegressor(
                n_estimators=1000,
                learning_rate=0.05,
                max_depth=6,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            ),
        ),
    ]
)

model_pipeline = TransformedTargetRegressor(
    regressor=feature_pipeline,
    func=np.log1p,
    inverse_func=np.expm1,
)

# ─── 6. Train / Test Split ────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ─── 7. Train ─────────────────────────────────────────────────────────────────
print("Training model…")
model_pipeline.fit(X_train, y_train)

# ─── 8. Evaluate ──────────────────────────────────────────────────────────────
y_pred = model_pipeline.predict(X_test)
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
print(f"R²  Score : {r2:.4f}")
print(f"MAE (INR) : ₹{mae:,.2f}  ← used as default confidence band")

# ─── 9. Feature Importance (for UI explanations) ──────────────────────────────
fitted_pipeline = model_pipeline.regressor_
feature_names = fitted_pipeline.named_steps["preprocessor"].get_feature_names_out()
feature_names = [name.split("__", 1)[-1] for name in feature_names]
importances = fitted_pipeline.named_steps["regressor"].feature_importances_
raw_importance = dict(zip(feature_names, importances.tolist()))
feature_importance = {}
for name, importance in raw_importance.items():
    base_name = name.split("_", 1)[0] if "_" in name and name.split("_", 1)[0] in categorical_cols else name
    feature_importance[base_name] = feature_importance.get(base_name, 0.0) + importance

# ─── 10. Save Model ───────────────────────────────────────────────────────────
model_path = os.path.join(model_dir, "laptop_price_model.pkl")
with open(model_path, "wb") as f:
    pickle.dump(model_pipeline, f)
print(f"Model saved → {model_path}")

# ─── 11. Save Metadata (categories + stats for UI) ────────────────────────────
metadata = {
    "categorical_cols": categorical_cols,
    "numerical_cols": numerical_cols,
    # Unique category values per column (cleaned, sorted)
    "categories": {
        col: sorted([str(v) for v in df[col].dropna().unique()])
        for col in categorical_cols
    },
    # Model performance stats — used to set default confidence band
    "mae": round(mae, 2),
    "r2": round(r2, 4),
    # Price range info for slider bounds
    "price_min": float(df["price"].min()),
    "price_max": float(df["price"].max()),
    "price_mean": float(df["price"].mean()),
    # Feature importance for explainability
    "feature_importance": feature_importance,
    "training_data_source": args.data_source,
    "training_rows": int(len(df)),
}

metadata_path = os.path.join(model_dir, "metadata.pkl")
with open(metadata_path, "wb") as f:
    pickle.dump(metadata, f)
print(f"Metadata saved → {metadata_path}")
print(f"\n✅ Ready. Default confidence band = ±₹{mae:,.0f}")
