import pandas as pd
import numpy as np
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ─── Paths ────────────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, "..", "data", "raw", "data_real.csv")
graphs_dir = os.path.join(script_dir, "..", "..", "assets", "graphs")
os.makedirs(graphs_dir, exist_ok=True)

# ─── 1. Load Data ─────────────────────────────────────────────────────────────
df = pd.read_csv(data_path)

# ─── 2. Data Cleaning ───────────────────────────────────────────────────────────
from data_cleaning import clean_laptop_data
df = clean_laptop_data(df)
df = df[(df["price"] >= 10000) & (df["price"] <= 500000)]

# ─── 3. Features, Preprocessing, Outliers ──────────────────────────────────────
from data_cleaning import prepare_training_data
X, y, preprocessor, df, categorical_cols, numerical_cols = prepare_training_data(df)


# ─── 4. Models to Compare ─────────────────────────────────────────────────────
from sklearn.model_selection import RandomizedSearchCV
from sklearn.ensemble import HistGradientBoostingRegressor

models = {
    "XGBoost (Baseline)": xgb.XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, random_state=42, verbosity=0),
    "Random Forest (Baseline)": RandomForestRegressor(n_estimators=100, random_state=42),
    "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, random_state=42),
    "Ridge Regression": Ridge(alpha=1.0),
    "Neural Network": MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=500, random_state=42, early_stopping=True),
    "Tuned Random Forest": RandomizedSearchCV(
        RandomForestRegressor(random_state=42, n_jobs=-1),
        param_distributions={
            'n_estimators': [100, 200],
            'max_depth': [15, None],
            'min_samples_split': [2, 5]
        },
        n_iter=3, cv=3, scoring='neg_mean_absolute_error', random_state=42, n_jobs=-1
    ),
    "HistGradientBoosting (Fast)": HistGradientBoostingRegressor(
        max_iter=500, learning_rate=0.05, max_depth=6, random_state=42
    )
}

results = {"Model": [], "R2 Score": [], "MAE (₹)": []}

kf = KFold(n_splits=5, shuffle=True, random_state=42)

for name, model in models.items():
    print(f"Evaluating {name}...")
    
    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("regressor", model)])
    model_pipeline = TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
    )
    
    cv_r2 = []
    cv_mae = []
    
    for train_idx, test_idx in kf.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        model_pipeline.fit(X_train, y_train)
        y_pred = model_pipeline.predict(X_test)
        
        cv_r2.append(r2_score(y_test, y_pred))
        cv_mae.append(mean_absolute_error(y_test, y_pred))
        
    mean_r2 = np.mean(cv_r2)
    mean_mae = np.mean(cv_mae)
    
    print(f"{name} - R2: {mean_r2:.4f}, MAE: ₹{mean_mae:.2f}")
    
    results["Model"].append(name)
    results["R2 Score"].append(mean_r2)
    results["MAE (₹)"].append(mean_mae)

# ─── 5. Generate Unified Graphs ───────────────────────────────────────────────
results_df = pd.DataFrame(results)
results_df = results_df.sort_values(by="R2 Score", ascending=False)

sns.set_theme(style="whitegrid")

# Graph 1: R2 Score Comparison
# The user specifically requested to keep the negative Neural Network score visible!
plot_df = results_df.copy()

plt.figure(figsize=(10, 6))
ax = sns.barplot(x="R2 Score", y="Model", data=plot_df, palette="viridis", hue="Model", legend=False)
plt.title("Algorithm Comparison: R² Score (Higher is Better)", fontsize=14, pad=15)
plt.xlim(0, 1.0)
for i, v in enumerate(plot_df["R2 Score"]):
    ax.text(v + 0.01, i, f"{v:.4f}", color='black', va='center', fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(graphs_dir, "r2_comparison.png"), dpi=300)
plt.close()

# Graph 2: MAE Comparison
results_df_mae = results_df.sort_values(by="MAE (₹)", ascending=True)
plt.figure(figsize=(10, 6))
ax = sns.barplot(x="MAE (₹)", y="Model", data=results_df_mae, palette="mako", hue="Model", legend=False)
plt.title("Algorithm Comparison: Mean Absolute Error (Lower is Better)", fontsize=14, pad=15)
for i, v in enumerate(results_df_mae["MAE (₹)"]):
    ax.text(v + 100, i, f"₹{v:,.0f}", color='black', va='center', fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(graphs_dir, "mae_comparison.png"), dpi=300)
plt.close()

print("Graphs generated in assets/graphs/")
print("\nFinal Results:")
print(results_df.to_string(index=False))
