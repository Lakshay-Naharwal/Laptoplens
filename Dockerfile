FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# System dependencies for optional Playwright/Selenium scraping.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Browser install is best-effort because live scraping is optional.
RUN playwright install chromium && playwright install-deps chromium

# Hugging Face Spaces require running as a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user backend/ ./backend/
COPY --chown=user --from=frontend-builder /build/frontend/dist ./frontend/dist

EXPOSE 7860

CMD ["sh", "-c", "PYTHONPATH=$HOME/app gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 1 --timeout 120 --access-logfile - backend.api.app:app"]
