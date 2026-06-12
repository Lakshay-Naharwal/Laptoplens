/**
 * api/client.js
 * Centralised Axios client for all Flask API calls.
 * Base URL is empty in dev (Vite proxies /api → Flask:5000).
 */

import axios from "axios";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export const apiUrl = (path) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

const api = axios.create({
  baseURL: API_BASE_URL,
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

export default api;
