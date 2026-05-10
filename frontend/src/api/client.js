/**
 * api/client.js
 * Centralised Axios client for all Flask API calls.
 * Base URL is empty in dev (Vite proxies /api → Flask:5000).
 */

import axios from "axios";

const api = axios.create({
  baseURL: "",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ── API methods ───────────────────────────────────────────────────────────────

/** Fetch form dropdown options and model stats. */
export const fetchMetadata = () => api.get("/api/metadata").then((r) => r.data);

/**
 * Predict laptop price.
 * @param {Object} specs - All feature values + optional confidence_band
 * @returns {Promise<{price, price_min, price_max, confidence_band, mae, formatted, formatted_range}>}
 */
export const predictPrice = (specs) =>
  api.post("/api/predict", specs).then((r) => r.data);

/**
 * Fetch laptop recommendations.
 * @param {Object} params - { predicted_price, confidence_band, use_case, ram, gpu_type, use_live? }
 * @returns {Promise<{laptops, source, cached}>}
 */
export const fetchRecommendations = (params) =>
  api.post("/api/recommend", params).then((r) => r.data);

/**
 * Fetch price history for a product.
 * @param {string} productId
 * @param {number} days - 7 | 30 | 90 | 180 | 365
 * @returns {Promise<{history, stats, tracking_started}>}
 */
export const fetchPriceHistory = (productId, days = 30) =>
  api
    .get("/api/price-history", { params: { product_id: productId, days } })
    .then((r) => r.data);

export default api;
