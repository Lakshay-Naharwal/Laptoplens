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

An AI-powered platform that predicts a fair laptop price, finds matching real-time listings, and tracks price history across Indian e-commerce platforms.

## Features

| Feature | Description |
|---|---|
| 🤖 **AI Price Prediction** | XGBoost model trained on 900+ laptops, predicts ±MAE accuracy |
| 🎚️ **Adjustable Tolerance** | You control the ±₹ confidence band (tight/flexible) |
| 📦 **Recommendation Cards** | Matching laptops with spec match scores |
| 📈 **Price History Chart** | Line chart with 7D/1M/3M/6M/1Y timeframes |
| 🏷️ **Use-Case Filter** | Gaming / Office / Design / Programming / General |
| 📝 **Mock → Live** | Demo works offline; live Flipkart scraper is optional |

## Tech Stack

- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: Flask 3 + Gunicorn
- **ML Model**: XGBoost + scikit-learn Pipeline
- **Database**: SQLite (price history, append-only)
- **Scraping**: Playwright (optional) + mock data fallback
- **Deployment**: Hugging Face Spaces (Docker)

## Local Development

### Backend (Flask)

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Train the model (first time only)
python train_model.py

# 4. Start Flask
python app.py
# → http://localhost:5000
```

By default, `train_model.py` uses the curated `data.csv`. Scraped `data_real.csv` is kept for recommendations because marketplace-title parsing can be noisy. To experiment with scraped training data, run `python train_model.py --data-source real`.

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
# Flask will serve this automatically
```

## Docker (local)

```bash
docker build -t laptoplens .
docker run -p 7860:7860 laptoplens
# → http://localhost:7860
```

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

> ⚠️ The `/data` directory on HF Spaces is the persistent volume — SQLite DB is stored there.

## Project Structure

```
laptop-price-prediction/
├── app.py                 # Flask API
├── train_model.py         # XGBoost training
├── data.csv               # Training dataset
├── requirements.txt
├── Dockerfile             # Multi-stage build
├── database/
│   ├── db.py              # SQLite CRUD
│   └── schema.sql
├── scraper/
│   ├── cache.py           # TTL in-memory cache
│   ├── mock_data.py       # Demo data generator
│   └── flipkart_scraper.py # Playwright scraper (optional)
├── model/                 # Trained model artifacts
└── frontend/              # React app
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   └── api/client.js
    ├── package.json
    └── vite.config.js
```

## Scraping Disclaimer

> Live scraping from Flipkart/Amazon may violate their Terms of Service.
> The Playwright scraper is included for educational purposes.
> For production, use the [Flipkart Affiliate API](https://affiliate.flipkart.com/) (free).

## License

MIT — Personal project, not for commercial redistribution of scraped data.
