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

# 1. Load Data
df = pd.read_csv('data.csv')

# 2. Preprocessing
# Drop redundant columns
df = df.drop(['Unnamed: 0.1', 'Unnamed: 0', 'name', 'CPU'], axis=1)

# Clean numeric columns
def extract_number(val):
    try:
        return float(''.join(filter(str.isdigit, str(val))))
    except:
        return 0.0

df['Ram'] = df['Ram'].apply(extract_number)

def clean_rom(val):
    val = str(val).upper()
    num = extract_number(val)
    if 'TB' in val:
        return num * 1024
    return num

df['ROM'] = df['ROM'].apply(clean_rom)

# 3. Define Features and Target
X = df.drop('price', axis=1)
y = df['price']

# Define categorical and numerical columns
categorical_cols = ['brand', 'processor', 'Ram_type', 'ROM_type', 'GPU', 'OS']
numerical_cols = ['spec_rating', 'Ram', 'ROM', 'display_size', 'resolution_width', 'resolution_height', 'warranty']

# 4. Create Preprocessing Pipeline
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), numerical_cols),
        ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), categorical_cols)
    ])

# 5. Define Model Pipeline
model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('regressor', xgb.XGBRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    ))
])

# 6. Train-Test Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 7. Train Model
print("Training model...")
model_pipeline.fit(X_train, y_train)

# 8. Evaluate Model
y_pred = model_pipeline.predict(X_test)
print(f"R2 Score: {r2_score(y_test, y_pred):.4f}")
print(f"Mean Absolute Error: {mean_absolute_error(y_test, y_pred):.2f}")

# 9. Save Model and Pipeline
os.makedirs('model', exist_ok=True)
with open('model/laptop_price_model.pkl', 'wb') as f:
    pickle.dump(model_pipeline, f)

print("Model saved to model/laptop_price_model.pkl")

# Save the list of categories for the UI
metadata = {
    'categorical_cols': categorical_cols,
    'numerical_cols': numerical_cols,
    'categories': {col: df[col].unique().tolist() for col in categorical_cols}
}
with open('model/metadata.pkl', 'wb') as f:
    pickle.dump(metadata, f)
