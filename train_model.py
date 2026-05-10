import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import pickle
import os

# ─── Paths ────────────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(script_dir, "model")
os.makedirs(model_dir, exist_ok=True)

# ─── 1. Load Data ─────────────────────────────────────────────────────────────
# Prefer real scraped data if available, fall back to bundled CSV
real_data_path = os.path.join(script_dir, "data_real.csv")
default_data_path = os.path.join(script_dir, "data.csv")
if os.path.exists(real_data_path):
    data_path = real_data_path
    print(f"✅ Using real scraped data: {real_data_path}")
else:
    data_path = default_data_path
    print(f"ℹ️  Using bundled data: {default_data_path} (run scraper to get real data)")
df = pd.read_csv(data_path)

# ─── 2. Preprocessing ─────────────────────────────────────────────────────────
# Drop redundant/identifier columns
drop_cols = [c for c in ["Unnamed: 0.1", "Unnamed: 0", "name", "CPU"] if c in df.columns]
df = df.drop(drop_cols, axis=1)


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


df["Ram"] = df["Ram"].apply(extract_number)
df["ROM"] = df["ROM"].apply(clean_rom)

# ─── 3. Features & Target ─────────────────────────────────────────────────────
categorical_cols = ["brand", "processor", "Ram_type", "ROM_type", "GPU", "OS"]
numerical_cols = [
    # spec_rating removed — it's a scraped/computed field users can't know
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
            OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
            categorical_cols,
        ),
    ]
)

# ─── 5. Model Pipeline ────────────────────────────────────────────────────────
model_pipeline = Pipeline(
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
feature_names = numerical_cols + categorical_cols
importances = model_pipeline.named_steps["regressor"].feature_importances_
feature_importance = dict(zip(feature_names, importances.tolist()))

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
}

metadata_path = os.path.join(model_dir, "metadata.pkl")
with open(metadata_path, "wb") as f:
    pickle.dump(metadata, f)
print(f"Metadata saved → {metadata_path}")
print(f"\n✅ Ready. Default confidence band = ±₹{mae:,.0f}")
