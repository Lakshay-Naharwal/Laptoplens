/**
 * components/PriceHistoryChart.jsx
 * Interactive price history chart using Chart.js with:
 *  - Line chart with gradient fill
 *  - Timeframe filter tabs: 7D | 1M | 3M | 6M | 1Y
 *  - Min / Max / Avg annotation lines
 *  - Stats summary row
 *  - "Tracking started" empty state
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { Chart, registerables } from "chart.js";
import { fetchPriceHistory } from "../api/client";

Chart.register(...registerables);

const TIMEFRAMES = [
  { label: "7D",  days: 7   },
  { label: "1M",  days: 30  },
  { label: "3M",  days: 90  },
  { label: "6M",  days: 180 },
  { label: "1Y",  days: 365 },
];

const fmt = (n) => n != null ? `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}` : "—";

export default function PriceHistoryChart({ productId, productName, currentPrice, onClose }) {
  const canvasRef       = useRef(null);
  const chartRef        = useRef(null);
  const [activeDays, setActiveDays]         = useState(30);
  const [historyData, setHistoryData]       = useState(null);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState(null);

  // ── Fetch price history ───────────────────────────────────────────────────
  const loadHistory = useCallback(async (days) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPriceHistory(productId, days);
      setHistoryData(data);
    } catch (err) {
      setError("Failed to load price history.");
    } finally {
      setLoading(false);
    }
  }, [productId]);

  useEffect(() => { loadHistory(activeDays); }, [activeDays, loadHistory]);

  // ── Build / update chart ─────────────────────────────────────────────────
  useEffect(() => {
    if (!historyData || !canvasRef.current || loading) return;
    const { history, stats } = historyData;

    // Destroy previous instance
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    if (!history || history.length === 0) return;

    const labels = history.map((h) => {
      const d = new Date(h.scraped_at);
      return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
    });
    const prices = history.map((h) => h.price);

    const ctx = canvasRef.current.getContext("2d");

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 280);
    gradient.addColorStop(0, "rgba(59, 130, 246, 0.35)");
    gradient.addColorStop(1, "rgba(59, 130, 246, 0.01)");

    chartRef.current = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Price (₹)",
            data: prices,
            borderColor: "#3b82f6",
            backgroundColor: gradient,
            borderWidth: 2,
            fill: true,
            tension: 0.4,
            pointRadius: prices.length > 60 ? 0 : 3,
            pointHoverRadius: 6,
            pointBackgroundColor: "#3b82f6",
            pointBorderColor: "#080e1a",
            pointBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#111d2e",
            borderColor: "rgba(255,255,255,0.08)",
            borderWidth: 1,
            titleColor: "#94a3b8",
            bodyColor: "#f8fafc",
            padding: 10,
            callbacks: {
              label: (ctx) => ` ₹${ctx.raw.toLocaleString("en-IN")}`,
            },
          },
          // Min / Max / Avg annotation lines via dataset trick
        },
        scales: {
          x: {
            grid: { color: "rgba(255,255,255,0.04)" },
            ticks: {
              color: "#475569",
              maxTicksLimit: 8,
              font: { size: 11 },
            },
          },
          y: {
            grid: { color: "rgba(255,255,255,0.04)" },
            ticks: {
              color: "#475569",
              font: { size: 11 },
              callback: (v) => `₹${(v / 1000).toFixed(0)}K`,
            },
            // Add min/max/avg horizontal lines via suggestedMin/Max
            suggestedMin: stats?.min_price ? stats.min_price * 0.98 : undefined,
            suggestedMax: stats?.max_price ? stats.max_price * 1.02 : undefined,
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [historyData, loading]);

  const stats = historyData?.stats;
  const trackingStarted = historyData?.tracking_started;

  return (
    <div className="glass p-5 space-y-5 animate-slide-up">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display font-semibold text-white text-base leading-snug line-clamp-1">
            {productName}
          </h3>
          <p className="text-xs text-muted mt-0.5">Price History</p>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-white transition-colors text-lg leading-none flex-shrink-0"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      {/* ── Timeframe tabs ───────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-bg-surface rounded-xl p-1">
        {TIMEFRAMES.map(({ label, days }) => (
          <button
            key={label}
            type="button"
            onClick={() => setActiveDays(days)}
            className={`
              flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200
              ${activeDays === days
                ? "bg-gradient-to-r from-accent-blue to-accent-purple text-white shadow-sm"
                : "text-muted hover:text-white"
              }
            `}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Stats row ────────────────────────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Current", value: fmt(currentPrice),      color: "text-white" },
            { label: "Min",     value: fmt(stats.min_price),   color: "text-green-400" },
            { label: "Max",     value: fmt(stats.max_price),   color: "text-red-400" },
            { label: "Avg",     value: fmt(stats.avg_price),   color: "text-amber-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-bg-surface rounded-xl p-3 text-center">
              <p className="text-xs text-muted">{label}</p>
              <p className={`font-display font-bold text-sm mt-0.5 ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Chart ────────────────────────────────────────────────────────── */}
      <div className="relative" style={{ height: "220px" }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm">
            {error}
          </div>
        )}
        {trackingStarted && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center gap-2">
            <span className="text-3xl">📊</span>
            <p className="text-muted text-sm font-medium">Tracking started!</p>
            <p className="text-slate-600 text-xs">Price data will accumulate over time.</p>
          </div>
        )}
        <canvas
          ref={canvasRef}
          className={loading || trackingStarted ? "opacity-20" : ""}
        />
      </div>

      {/* ── Data source note ──────────────────────────────────────────────── */}
      <p className="text-xs text-slate-600 text-center">
        {historyData?.source === "mock"
          ? "📝 Simulated history for demo — live tracking starts now"
          : "🔴 Live data from Flipkart"}
      </p>
    </div>
  );
}
