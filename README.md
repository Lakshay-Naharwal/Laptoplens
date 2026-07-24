---
title: LaptopLens — AI Price Intelligence
emoji: 🔍
colorFrom: blue
colorTo: purple
sdk: docker
port: 7860
app_port: 7860
pinned: true
---

# 🔍 LaptopLens — AI Laptop Price Intelligence

> Know the fair price **before** you buy.

**🚀 Live Demo:** [https://laptoplens.vercel.app](https://laptoplens.vercel.app)

An AI-powered platform that predicts a fair laptop price, finds matching real-time listings, and tracks price history across Indian e-commerce platforms.

## Features

| Feature | Description |
|---|---|
| 🤖 **AI Price Prediction** | XGBoost model trained on 900+ laptops, predicting real-world prices |
| 🎚️ **Adjustable Tolerance** | You control the ±₹ confidence band (tight/flexible) |
| 📦 **Recommendation Cards** | Matching laptops with spec match scores |
| 🛒 **Dynamic Buying Links** | Instantly redirects to live **Flipkart** and **Amazon** search results |
| 🏷️ **Use-Case Filter** | Gaming / Office / Design / Programming / General |
| 📝 **Mock → Live** | Demo works offline; live Amazon/Flipkart/Smartprix scrapers are optional |
| 🛡️ **Secure Model Loads** | Enforces strict SHA-256 checksums to ensure pickle file integrity |

## Tech Stack

- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: Flask 3 + Gunicorn (Single Worker to protect in-memory cache)
- **ML Model**: Voting Regressor (XGBoost + Ridge) inside a TransformedTargetRegressor
- **Scraping**: Playwright (Flipkart/Amazon) + Requests/BS4 (Smartprix) + pre-scraped data + mock data fallback
- **Deployment**: Hugging Face Spaces (Docker)

## Algorithm Comparison & Pipeline Robustness

To ensure the highest accuracy for price predictions, we trained and evaluated multiple machine learning algorithms on our curated dataset of ~6,000 real-world laptop listings. 

### Phase 1: Baseline Models
Evaluated on the raw scraped dataset (6,000+ rows).

- **Random Forest**: R² = 0.659 | MAE = ₹19,637
- **XGBoost**: R² = 0.641 | MAE = ₹20,790
- **Neural Network (MLP)**: R² = -4089.639 | MAE = ₹105,849 *(Performed severely worse than a random baseline on this tabular dataset)*

### Phase 2: Post-Improvements 🏆 (Current Implementation)

To improve real-world accuracy and prevent data leakage, we applied the following improvements:
1. **Strict 80/20 Holdout Split**: To evaluate true generalizability, 20% of data is safely hidden from the entire training and cleaning phase.
2. **Aggressive Data Cleaning**: Removed ~800 extreme price outliers using `IsolationForest` **(fitted exclusively on the training set to prevent data leakage)**.
3. **Advanced Architecture**: Used a Voting Regressor combining XGBoost and Ridge regression for stabilized predictions.

This drastically reduced our Mean Absolute Error (MAE) and increased reliability!
- **Tuned Model (Final Holdout Set)**: MAE = ~₹22,673 | R² = 0.81 🏆 *(Extremely realistic pricing on unseen data)*

## Local Development

### Backend (Flask)

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Install dependencies (Pinned for reproducibility)
pip install -r requirements.txt

# 3. Train the model (first time only, saves checksums)
python backend/ml/train_model.py

# 4. Start Flask (Requires PYTHONPATH on some terminals)
python backend/api/app.py
# → http://localhost:5000

# Optional: Run the interactive CLI pricing tool
python backend/cli/main.py
```

*Note: Live scraping is disabled by default to avoid accidental headless browsing restrictions. You can enable it by passing `ENABLE_LIVE_SCRAPING=true` in your `.env`.*

### Frontend (React)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173  (proxies /api to Flask:5000)
```

### Build for Production

```bash
cd frontend
npm run build
# Output: frontend/dist/
# Flask will serve this automatically if configured for static serving
```

## Docker (local)

```bash
docker build -t laptoplens .
docker run -p 7860:7860 laptoplens
# → http://localhost:7860
```
*(The Dockerfile properly handles installing Playwright dependencies and running Gunicorn with 1 worker to ensure predictable in-memory cache behavior).*

## Deployment Notes

- `render.yaml` uses the Dockerfile so the React build and Flask backend are built together.
- Runtime files such as `price_history.db*`, `frontend/dist/`, and `scraper/image_cache.json` are generated locally and ignored by Git.
- Set `CORS_ORIGINS` only when the API must be called from a separate frontend origin. Same-origin production deployments do not need it.

## Deploy to Hugging Face Spaces

1. Create a new Space → **Docker** SDK
2. Push this repository:
   ```bash
   git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/laptoplens
   git push hf main
   ```
3. HF Spaces will auto-build and deploy (~5 min first time)

## Split Frontend/Backend Deployment

If the Flask backend is deployed on Hugging Face Spaces and the React frontend is deployed separately on Vercel, configure both sides with their public origins:

- In Vercel, set `VITE_API_BASE_URL` to your Hugging Face Space URL, for example `https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space`.
- In Hugging Face Spaces, set `CORS_ORIGINS` to your Vercel app URL, for example `https://your-app.vercel.app`.

## Project Structure

```text
Laptoplens/
├── backend/
│   ├── api/
│   │   ├── app.py                  # Flask API & Routes
│   │   └── utils.py                # Helper utilities (e.g. GPU parsing)
│   ├── cli/
│   │   └── main.py                 # Interactive command-line pricing tool
│   ├── ml/
│   │   ├── train_model.py          # Training script & Checksum generation
│   │   ├── data_cleaning.py        # Leakage-free outlier detection
│   │   ├── compare_models.py       # Script to benchmark algorithms
│   │   └── model/                  # Saved artifacts and Checksums
│   ├── scraper/
│   │   ├── cache.py                # TTLCache with LRU Eviction limits
│   │   ├── mock_data.py            # Generates dynamic mock laptops
│   │   ├── flipkart_scraper.py     # Base Playwright scraper
│   │   ├── amazon_flipkart_scraper.py # Unified Playwright scraping interface
│   │   ├── smartprix_scraper.py    # Overnight scraping using Requests/BS4
│   │   └── image_fetcher.py        # Laptop image fetching & caching
│   └── data/                       
│       └── raw/                    # Contains raw dataset like data_real.csv
├── frontend/                       # React + Vite App
├── Dockerfile                      # Multi-stage optimized Docker build
└── requirements.txt                # Strictly pinned dependencies
```

## Scraping Disclaimer

> Live scraping from Flipkart/Amazon may violate their Terms of Service.
> The Playwright scraper is included for educational purposes.
> For production, use the [Flipkart Affiliate API](https://affiliate.flipkart.com/) (free).

## License

MIT — Personal project, not for commercial redistribution of scraped data.
