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
data_path = os.path.join(script_dir, "..", "data", "raw", "data_real.csv")
if not os.path.exists(data_path):
    raise FileNotFoundError(f"Training data not found: {data_path}")
print(f"Training source: {data_path}")

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

import sys
sys.path.append(os.path.join(script_dir, ".."))
from api.utils import get_cores, get_threads, get_cpu_brand, get_cpu_tier, get_cpu_gen, get_gpu_brand, get_gpu_vram

# Initial cleaning
def clean_os(val):
    val = str(val).upper()
    if '11' in val and 'WINDOWS' in val: return 'Windows 11'
    if '10' in val and 'WINDOWS' in val: return 'Windows 10'
    if 'WINDOWS' in val: return 'Windows'
    if 'MAC' in val: return 'macOS'
    if 'CHROME' in val: return 'ChromeOS'
    if 'UBUNTU' in val: return 'Ubuntu'
    if 'DOS' in val: return 'DOS'
    if 'ANDROID' in val: return 'Android'
    return val.strip().title()

def clean_gpu(val):
    import re
    val = str(val).strip().upper()
    for word in ['GRAPHICS', 'GRAPHIC', 'GRAPHIICS', 'INTEGRATED', 'GEFORCE', '']:
        val = val.replace(word, '')
    val = ' '.join(val.split())
    
    val = val.replace('NVIDIA', 'NVIDIA').replace('AMD', 'AMD').replace('INTEL', 'Intel').replace('APPLE', 'Apple')
    val = val.replace('RTX', 'RTX ').replace('GTX', 'GTX ').replace('RX', 'RX ')
    val = val.replace('UHD', 'UHD').replace('IRIS XE', 'Iris Xe').replace('IRIS X', 'Iris Xe')
    
    val = re.sub(r'(RTX|GTX|RX)(\d)', r'\1 \2', val)
    
    words = val.split()
    unique_words = []
    for w in words:
        if w not in unique_words and w != 'GB':
            unique_words.append(w)
    val = ' '.join(unique_words)
    
    m = re.search(r'(\d+)\s*GB', val, flags=re.IGNORECASE)
    if m:
        vram = m.group(1) + 'GB'
        val = re.sub(r'\d+\s*GB', '', val, flags=re.IGNORECASE)
        val = val.strip() + ' ' + vram
        
    return val if val else 'Other'

df["Ram"] = df["Ram"].apply(extract_number)
df["ROM"] = df["ROM"].apply(clean_rom)
df["OS"] = df["OS"].apply(clean_os)
df["GPU"] = df["GPU"].apply(clean_gpu)
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df = df.dropna(subset=["price"])
df = df[(df["price"] >= 10000) & (df["price"] <= 500000)]

# ─── 3. Features & Target ─────────────────────────────────────────────────────
categorical_cols = ["brand", "processor", "Ram_type", "ROM_type", "GPU", "OS"]
numerical_cols = [
    "Ram",
    "ROM",
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

# ─── 6. Train / Test Split & K-Fold Evaluation ────────────────────────────────
from sklearn.model_selection import KFold
import numpy as np

print("Running K-Fold Cross Validation (5 folds)…")
kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_r2_scores = []
cv_mae_scores = []

for fold, (train_idx, test_idx) in enumerate(kf.split(X)):
    X_train_cv, X_test_cv = X.iloc[train_idx], X.iloc[test_idx]
    y_train_cv, y_test_cv = y.iloc[train_idx], y.iloc[test_idx]
    
    model_pipeline.fit(X_train_cv, y_train_cv)
    y_pred_cv = model_pipeline.predict(X_test_cv)
    
    cv_r2_scores.append(r2_score(y_test_cv, y_pred_cv))
    cv_mae_scores.append(mean_absolute_error(y_test_cv, y_pred_cv))
    print(f"  Fold {fold+1}: R² = {cv_r2_scores[-1]:.4f}, MAE = ₹{cv_mae_scores[-1]:,.2f}")

print(f"\n--- Cross-Validation Results ---")
print(f"Mean R²:  {np.mean(cv_r2_scores):.4f} (±{np.std(cv_r2_scores):.4f})")
print(f"Mean MAE: ₹{np.mean(cv_mae_scores):,.2f} (±₹{np.std(cv_mae_scores):,.2f})")
print(f"--------------------------------\n")

# ─── 7. Train Final Model on All Data ─────────────────────────────────────────
print("Training final model on all data…")
model_pipeline.fit(X, y)

# ─── 8. Evaluate ──────────────────────────────────────────────────────────────
# We use the mean MAE and R2 from CV for metadata
r2 = float(np.mean(cv_r2_scores))
mae = float(np.mean(cv_mae_scores))
print(f"Final Model (trained on all data) will use CV MAE as default confidence band: ±₹{mae:,.2f}")

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
    "training_rows": int(len(df)),
}

metadata_path = os.path.join(model_dir, "metadata.pkl")
with open(metadata_path, "wb") as f:
    pickle.dump(metadata, f)
print(f"Metadata saved → {metadata_path}")
print(f"\n✅ Ready. Default confidence band = ±₹{mae:,.0f}")
