# ════════════════════════════════════════════════════════════
#  Stage 1 — Build React frontend
# ════════════════════════════════════════════════════════════
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

# Install deps first (better layer caching)
COPY frontend/package*.json ./
RUN npm ci --silent

# Copy source and build
COPY frontend/ ./
RUN npm run build
# Output: /build/frontend/dist/


# ════════════════════════════════════════════════════════════
#  Stage 2 — Python backend + serve React
# ════════════════════════════════════════════════════════════
FROM python:3.11-slim

# System deps for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python dependencies ──────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright + Chromium (optional — won't fail if not used)
RUN pip install --no-cache-dir playwright \
    && playwright install chromium \
    && playwright install-deps chromium \
    || echo "Playwright install failed — live scraping disabled"

# ── Application code ─────────────────────────────────────────
COPY app.py train_model.py ./
COPY data.csv ./
COPY data_real.csv ./
COPY database/ ./database/
COPY scraper/  ./scraper/

# ── Copy React build from Stage 1 ────────────────────────────
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# ── Create persistent data directory (HF Spaces mounts /data) ─
RUN mkdir -p /data

# ── Train model if not already present ───────────────────────
# (In production, pre-train and include the model/ directory)
RUN python train_model.py || echo "Model training skipped (pre-trained model expected)"

# ── Expose port (HF Spaces uses 7860) ────────────────────────
EXPOSE 7860

# ── Run gunicorn ─────────────────────────────────────────────
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 2 --timeout 120 --access-logfile - app:app"]
