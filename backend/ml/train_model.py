import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, VotingRegressor
from sklearn.linear_model import Ridge
import pickle
import os
import argparse
import sys
import json
import hashlib

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
from data_cleaning import clean_laptop_data
df = clean_laptop_data(df)

# ─── 3. Features & Target / 4. Preprocessing ──────────────────────────────────
from data_cleaning import get_features_and_preprocessor
X, y, preprocessor, categorical_cols, numerical_cols = get_features_and_preprocessor(df)

# ─── 4.5 Train/Test Split ─────────────────────────────────────────────────────
print("Splitting data into 80% train and 20% holdout test set...")
X_train_full, X_test_holdout, y_train_full, y_test_holdout = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ─── 4.6 Feature-Based Outlier Removal (on train only) ────────────────────────
print("Running feature-based outlier detection on training data...")
from sklearn.model_selection import cross_val_predict
X_train_prep = preprocessor.fit_transform(X_train_full)
rf_outlier = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
preds = cross_val_predict(rf_outlier, X_train_prep, np.log1p(y_train_full), cv=3, n_jobs=-1)
preds_real = np.expm1(preds)
ratio = y_train_full / preds_real

valid_mask = (ratio < 3.0) & (ratio > 0.33)
X_train = X_train_full[valid_mask]
y_train = y_train_full[valid_mask]
print(f"Removed {len(ratio) - valid_mask.sum()} mispriced laptops from training data. Remaining: {len(X_train)}")

# ─── 4.7 Monotonic Constraints ──────────────────────────────────────────────────
preprocessor.set_output(transform="pandas")
monotone_constraints = {"num__Ram": 1, "num__ROM": 1}

# ─── 5. Model Pipeline ────────────────────────────────────────────────────────
feature_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "regressor",
            VotingRegressor(
                estimators=[
                    (
                        "xgb", 
                        xgb.XGBRegressor(
                            n_estimators=500, 
                            learning_rate=0.05, 
                            max_depth=7, 
                            random_state=42, 
                            n_jobs=-1,
                            monotone_constraints=monotone_constraints
                        )
                    ),
                    (
                        "ridge", 
                        Ridge(alpha=10.0)
                    )
                ],
                weights=[0.8, 0.2]
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

for fold, (train_idx, test_idx) in enumerate(kf.split(X_train)):
    X_train_cv, X_test_cv = X_train.iloc[train_idx], X_train.iloc[test_idx]
    y_train_cv, y_test_cv = y_train.iloc[train_idx], y_train.iloc[test_idx]
    
    model_pipeline.fit(X_train_cv, y_train_cv)
    y_pred_cv = model_pipeline.predict(X_test_cv)
    
    cv_r2_scores.append(r2_score(y_test_cv, y_pred_cv))
    cv_mae_scores.append(mean_absolute_error(y_test_cv, y_pred_cv))
    print(f"  Fold {fold+1}: R² = {cv_r2_scores[-1]:.4f}, MAE = ₹{cv_mae_scores[-1]:,.2f}")

print(f"\n--- Cross-Validation Results ---")
print(f"Mean R²:  {np.mean(cv_r2_scores):.4f} (±{np.std(cv_r2_scores):.4f})")
print(f"Mean MAE: ₹{np.mean(cv_mae_scores):,.2f} (±₹{np.std(cv_mae_scores):,.2f})")
print(f"--------------------------------\n")

# ─── 7. Train Final Model on Cleaned Training Data ────────────────────────────
print("Training final model on cleaned training data…")
model_pipeline.fit(X_train, y_train)

# ─── 8. Evaluate on Holdout Set ───────────────────────────────────────────────
y_pred_holdout = model_pipeline.predict(X_test_holdout)
holdout_r2 = r2_score(y_test_holdout, y_pred_holdout)
holdout_mae = mean_absolute_error(y_test_holdout, y_pred_holdout)

print(f"\n--- Holdout Set Results ---")
print(f"Holdout R²:  {holdout_r2:.4f}")
print(f"Holdout MAE: ₹{holdout_mae:,.2f}")
print(f"---------------------------\n")

# We use the mean MAE and R2 from CV for metadata defaults (more stable representation)
r2 = float(np.mean(cv_r2_scores))
mae = float(np.mean(cv_mae_scores))
print(f"Final Model will use CV MAE as default confidence band: ±₹{mae:,.2f}")

# ─── 9. Feature Importance (for UI explanations) ──────────────────────────────
fitted_pipeline = model_pipeline.regressor_
feature_names = fitted_pipeline.named_steps["preprocessor"].get_feature_names_out()
feature_names = [name.split("__", 1)[-1] for name in feature_names]
importances = fitted_pipeline.named_steps["regressor"].estimators_[0].feature_importances_
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
    "categories": {
        col: sorted([str(v) for v in df[col].dropna().unique()])
        for col in categorical_cols
    },
    "mae": round(mae, 2),
    "r2": round(r2, 4),
    "holdout_mae": round(float(holdout_mae), 2),
    "holdout_r2": round(float(holdout_r2), 4),
    "price_min": float(df["price"].min()),
    "price_max": float(df["price"].max()),
    "price_mean": float(df["price"].mean()),
    "feature_importance": feature_importance,
    "training_rows": int(len(X_train)),
}

metadata_path = os.path.join(model_dir, "metadata.pkl")
with open(metadata_path, "wb") as f:
    pickle.dump(metadata, f)
print(f"Metadata saved → {metadata_path}")

# ─── 12. Generate Checksums ───────────────────────────────────────────────────
def get_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

checksums = {
    "laptop_price_model.pkl": get_file_hash(model_path),
    "metadata.pkl": get_file_hash(metadata_path)
}

checksums_path = os.path.join(model_dir, "checksums.json")
with open(checksums_path, "w") as f:
    json.dump(checksums, f, indent=4)
print(f"Checksums saved → {checksums_path}")

print(f"\n✅ Ready. Default confidence band = ±₹{mae:,.0f}")
