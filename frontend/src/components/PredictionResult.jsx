/**
 * components/PredictionResult.jsx
 * Shows the ML price prediction with:
 *  - Animated price reveal
 *  - Min/Max confidence band bar (user-adjustable)
 *  - "Find Matching Laptops" CTA
 *  - Feature importance breakdown (collapsible)
 */

import { useEffect, useRef, useState } from "react";

/** Animates a number counter from 0 to target. */
function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!target) return;
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration]);
  return value;
}

const fmt = (n) =>
  n?.toLocaleString("en-IN", { maximumFractionDigits: 0 }) ?? "—";

export default function PredictionResult({ result, onFindLaptops, isLoadingRecs }) {
  const animatedPrice = useCountUp(result?.price ?? 0);
  const [showImportance, setShowImportance] = useState(false);
  const [priceTolerance, setPriceTolerance] = useState(null); // null = use model MAE

  // Reset tolerance when a new prediction arrives
  useEffect(() => {
    setPriceTolerance(null);
  }, [result?.price]);

  if (!result) {
    return (
      <div className="glass p-6 flex flex-col items-center justify-center text-center gap-4 min-h-[260px]">
        {/* Placeholder state */}
        <div className="w-20 h-20 rounded-full bg-bg-surface border border-white/6 flex items-center justify-center text-4xl">
          💡
        </div>
        <div>
          <h2 className="font-display text-lg font-semibold text-white">Awaiting Analysis</h2>
          <p className="text-muted text-sm mt-1 max-w-xs">
            Fill in the specs and click Predict Price to see the AI-estimated market value.
          </p>
        </div>
      </div>
    );
  }

  const { price, price_min, price_max, confidence_band, mae, formatted_range, feature_importance } = result;

  // Band bar percentage fill (price_min → price_max within a ±30K window)
  const windowHalf = confidence_band * 1.5;
  const windowMin  = Math.max(price - windowHalf, 0);
  const windowMax  = price + windowHalf;
  const range      = windowMax - windowMin;
  const minPct     = ((price_min - windowMin) / range) * 100;
  const maxPct     = ((price_max - windowMin) / range) * 100;
  const pricePct   = ((price - windowMin) / range) * 100;

  // Sort feature importance for display
  const importanceEntries = feature_importance
    ? Object.entries(feature_importance).sort((a, b) => b[1] - a[1]).slice(0, 6)
    : [];
  const maxImp = importanceEntries[0]?.[1] ?? 1;

  return (
    <div className="glass p-6 space-y-5 animate-slide-up">
      {/* ── Price display ────────────────────────────────────────────────── */}
      <div className="text-center space-y-1">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
          AI Estimated Price
        </p>
        <div className="font-display font-bold text-5xl leading-none gradient-text">
          ₹{fmt(animatedPrice)}
        </div>
        <p className="text-muted text-sm">{formatted_range}</p>
      </div>

      {/* ── Band visualiser ───────────────────────────────────────────────── */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted">
          <span>₹{fmt(price_min)}</span>
          <span className="text-accent-blue font-medium">Fair Price</span>
          <span>₹{fmt(price_max)}</span>
        </div>
        {/* Track */}
        <div className="relative h-3 bg-bg-surface rounded-full overflow-hidden">
          {/* Band fill */}
          <div
            className="absolute h-full rounded-full opacity-40"
            style={{
              left:  `${minPct}%`,
              width: `${maxPct - minPct}%`,
              background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
            }}
          />
          {/* Predicted price marker */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow-glow-blue border-2 border-accent-blue"
            style={{ left: `calc(${pricePct}% - 6px)` }}
          />
        </div>
        <p className="text-xs text-slate-500 text-center">
          Model MAE: ±₹{fmt(mae)}
        </p>
      </div>

      {/* ── Price Tolerance Slider (controls Find Matching range) ──────────── */}
      {(() => {
        const band     = priceTolerance ?? mae;
        const rangeMin = Math.max(price - band, 0);
        const rangeMax = price + band;
        const fillPct  = ((band - 1000) / (50000 - 1000)) * 100;
        return (
          <div className="glass p-4 space-y-3" style={{ background: "rgba(255,255,255,0.03)" }}>
            <div className="flex items-center justify-between">
              <label
                htmlFor="price-tolerance-slider"
                className="text-xs font-semibold text-slate-400 uppercase tracking-widest"
              >
                Match Range
              </label>
              <span className="text-sm font-bold gradient-text">±₹{fmt(band)}</span>
            </div>
            <input
              id="price-tolerance-slider"
              type="range"
              min={1000} max={50000} step={500}
              value={band}
              onChange={(e) => {
                const v = Number(e.target.value);
                e.target.style.setProperty("--fill", `${((v-1000)/(50000-1000))*100}%`);
                setPriceTolerance(v);
              }}
              className="w-full"
              style={{ "--fill": `${fillPct}%` }}
            />
            <div className="flex justify-between text-xs text-muted">
              <span>₹{fmt(rangeMin)}</span>
              <span className="text-slate-500">Laptops sorted within this range</span>
              <span>₹{fmt(rangeMax)}</span>
            </div>
          </div>
        );
      })()}

      {/* ── Feature importance ────────────────────────────────────────────── */}
      {importanceEntries.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowImportance((v) => !v)}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1"
          >
            <span>{showImportance ? "▾" : "▸"}</span>
            What drives this price?
          </button>
          {showImportance && (
            <div className="mt-3 space-y-2 animate-fade-in">
              {importanceEntries.map(([feat, imp]) => (
                <div key={feat} className="flex items-center gap-3">
                  <span className="text-xs text-muted w-32 truncate capitalize">
                    {feat.replace(/_/g, " ")}
                  </span>
                  <div className="flex-1 h-1.5 bg-bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent-blue to-accent-purple"
                      style={{ width: `${(imp / maxImp) * 100}%`, transition: "width 0.6s ease" }}
                    />
                  </div>
                  <span className="text-xs text-muted w-10 text-right">
                    {(imp * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <button
        onClick={() => onFindLaptops(priceTolerance ?? mae)}
        disabled={isLoadingRecs}
        className="btn-gradient w-full py-3 rounded-xl font-display font-semibold text-sm flex items-center justify-center gap-2"
      >
        {isLoadingRecs ? (
          <>
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Finding Laptops…
          </>
        ) : (
          <>🔍 Find Matching Laptops</>
        )}
      </button>
    </div>
  );
}
