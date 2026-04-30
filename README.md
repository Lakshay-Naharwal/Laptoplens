---
title: Laptop Price Predictor
emoji: 💻
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# 💻 Laptop Price Predictor

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![XGBoost](https://img.shields.io/badge/Model-XGBoost-orange.svg)](https://xgboost.readthedocs.io/)
[![Scikit-Learn](https://img.shields.io/badge/Library-Scikit--Learn-green.svg)](https://scikit-learn.org/)
[![Flask](https://img.shields.io/badge/Web-Flask-black.svg)](https://flask.palletsprojects.com/)

An end-to-end machine learning project designed to predict the market price of laptops based on their technical specifications. Utilizing the power of **XGBoost** and a robust **Scikit-Learn pipeline**, this tool provides accurate price estimations through a beautiful, modern Web UI and a command-line interface.

---

## 🚀 Features

- **High Precision Modeling**: Built with `XGBRegressor` for state-of-the-art performance.
- **Automated Pipeline**: Handles data preprocessing (Scaling, Ordinal Encoding) seamlessly.
- **Beautiful Web UI**: Premium design with glassmorphism, responsive layouts, and smooth animations.
- **Interactive CLI**: Easy-to-use command-line interface available for terminal enthusiasts.
- **Comprehensive Specs**: Considers 13+ features including CPU, GPU, RAM, ROM, and Display quality.

## 🛠️ Technology Stack

- **Core**: Python 3.8+
- **Data Handling**: Pandas, NumPy
- **Machine Learning**: Scikit-Learn, XGBoost
- **Backend UI**: Flask
- **Frontend UI**: HTML5, Vanilla CSS3 (Glassmorphism), Vanilla JS

## 📁 Project Structure

```text
laptop-price-prediction/
├── data.csv                # Raw dataset
├── app.py                  # Flask Web UI server
├── main.py                 # CLI interface for predictions
├── train_model.py          # Model training & preprocessing script
├── requirements.txt        # Project dependencies
├── templates/              # HTML Templates for the UI
│   └── index.html
├── static/                 # CSS/JS for the UI
│   ├── style.css
│   └── script.js
├── model/                  # Saved artifacts
│   ├── laptop_price_model.pkl
│   └── metadata.pkl
└── README.md               # Project documentation
```

## ⚙️ Installation & Setup

We recommend using a Python Virtual Environment (`venv`) to run this project.

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\Activate.ps1
   # Mac/Linux:
   source venv/bin/activate
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

### 1. Web UI (Recommended)
Run the Flask server to interact with the model via a beautiful web interface.
```bash
python app.py
```
Then, open your web browser and navigate to `http://127.0.0.1:5000`.

### 2. Command Line Interface (CLI)
Run the prediction script and follow the interactive prompts:
```bash
python main.py
```

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
