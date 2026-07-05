import re
import pandas as pd
import numpy as np
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_predict

def extract_number(val):
    try:
        digits = "".join(filter(lambda c: c.isdigit() or c == ".", str(val)))
        return float(digits) if digits else 0.0
    except Exception:
        return 0.0

def clean_rom(val):
    val = str(val).upper()
    num = extract_number(val)
    return num * 1024 if "TB" in val else num

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

VALID_BRANDS = [
    "ASUS", "HP", "Dell", "Lenovo", "Acer", "MSI", "Apple", 
    "Samsung", "Xiaomi", "Mi", "Realme", "Infinix", "LG", "Honor", 
    "Avita", "Microsoft", "Razer", "Gigabyte", "Fujitsu", "Panasonic", "Vaio", "Chuwi"
]

def clean_brand(val):
    val = str(val).strip()
    upper = val.upper()
    for b in VALID_BRANDS:
        if b.upper() in upper:
            return b
    return "Other"

def clean_laptop_data(df):
    """
    Applies common string cleaning to laptop specifications
    and drops rows with missing prices or basic out-of-bounds prices.
    """
    df_clean = df.copy()
    df_clean["brand"] = df_clean["brand"].apply(clean_brand)
    df_clean["Ram"] = df_clean["Ram"].apply(extract_number)
    df_clean["ROM"] = df_clean["ROM"].apply(clean_rom)
    df_clean["OS"] = df_clean["OS"].apply(clean_os)
    df_clean["GPU"] = df_clean["GPU"].apply(clean_gpu)
    df_clean["price"] = pd.to_numeric(df_clean["price"], errors="coerce")
    df_clean = df_clean.dropna(subset=["price"])
    # Basic logical bounds (advanced feature-based bounds are applied separately during ML tuning)
    df_clean = df_clean[(df_clean["price"] >= 10000) & (df_clean["price"] <= 1000000)]
    return df_clean

def get_features_and_preprocessor(df):
    categorical_cols = ["brand", "processor", "Ram_type", "ROM_type", "GPU", "OS"]
    numerical_cols = [
        "Ram", "ROM", "display_size", "resolution_width", "resolution_height", "warranty"
    ]
    
    categorical_cols = [c for c in categorical_cols if c in df.columns]
    numerical_cols = [c for c in numerical_cols if c in df.columns]

    X = df[categorical_cols + numerical_cols]
    y = df["price"]

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
    
    return X, y, preprocessor, categorical_cols, numerical_cols
