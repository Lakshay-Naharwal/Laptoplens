# 💻 Laptop Price Predictor

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![XGBoost](https://img.shields.io/badge/Model-XGBoost-orange.svg)](https://xgboost.readthedocs.io/)
[![Scikit-Learn](https://img.shields.io/badge/Library-Scikit--Learn-green.svg)](https://scikit-learn.org/)

An end-to-end machine learning project designed to predict the market price of laptops based on their technical specifications. Utilizing the power of **XGBoost** and a robust **Scikit-Learn pipeline**, this tool provides accurate price estimations through a user-friendly command-line interface.

---

## 🚀 Features

- **High Precision Modeling**: Built with `XGBRegressor` for state-of-the-art performance.
- **Automated Pipeline**: Handles data preprocessing (Scaling, Ordinal Encoding) seamlessly.
- **Interactive CLI**: Easy-to-use interface for real-time predictions.
- **Smart Input Matching**: Loose-string matching for categorical inputs to minimize user errors.
- **Comprehensive Specs**: Considers 13+ features including CPU, GPU, RAM, ROM, and Display quality.

## 🛠️ Technology Stack

- **Core**: Python 3.8+
- **Data Handling**: Pandas, NumPy
- **Machine Learning**: Scikit-Learn, XGBoost
- **Serialization**: Pickle (for model persistence)

## 📁 Project Structure

```text
laptop-price-prediction/
├── data.csv                # Raw dataset
├── main.py                 # CLI interface for predictions
├── train_model.py          # Model training & preprocessing script
├── model/                  # Saved artifacts
│   ├── laptop_price_model.pkl
│   └── metadata.pkl
└── README.md               # Project documentation
```

## ⚙️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/laptop-price-prediction.git
   cd laptop-price-prediction
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Train the model**:
   Before running predictions, generate the model artifacts by training on the dataset:
   ```bash
   python train_model.py
   ```

## 🖥️ Usage

Run the prediction script and follow the interactive prompts:

```bash
python main.py
```

### Example Input Flow:
1. Select Brand (e.g., HP, Dell, Apple)
2. Select Processor (e.g., Core i5, Ryzen 7)
3. Enter RAM size (e.g., 16)
4. Enter ROM size (e.g., 512)
5. ... and other technical specs.

## 📊 Dataset Overview

The model is trained on a comprehensive dataset (`data.csv`) containing various laptop configurations. Key features include:
- **Categorical**: Brand, Processor, RAM Type, ROM Type, GPU, OS.
- **Numerical**: Spec Rating, RAM (GB), ROM (GB), Display Size, Resolution, Warranty.

## 📈 Performance

The model evaluation results (calculated on an 80/20 train-test split):
- **R² Score**: ~0.85+ (Varies slightly based on training)
- **Mean Absolute Error (MAE)**: Provides realistic price deviation based on market volatility.

---

*Developed with ❤️ for the Developer Community.*
