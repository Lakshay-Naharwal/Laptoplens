/**
 * components/RecommendationCard.jsx
 * Renders a single laptop recommendation card with:
 *  - Real product image (lazy-loaded from /api/laptop-image with skeleton shimmer)
 *  - Color-coded match score bar
 *  - Price vs. prediction band comparison badge (soft filter: in/out of range)
 */

import { useState, useEffect } from "react";
import { apiUrl } from "../api/client";

const fmt = (n) => n?.toLocaleString("en-IN", { maximumFractionDigits: 0 }) ?? "—";

/** Returns color classes for a match score 0–100 */
function scoreColor(score) {
  if (score >= 80) return { bar: "from-green-500 to-emerald-400", badge: "text-green-400 bg-green-400/10 border-green-400/20" };
  if (score >= 60) return { bar: "from-yellow-500 to-amber-400", badge: "text-amber-400 bg-amber-400/10 border-amber-400/20" };
  return { bar: "from-red-500 to-orange-400", badge: "text-red-400 bg-red-400/10 border-red-400/20" };
}

/** Spec chip */
function SpecChip({ label, value }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-bg-surface border border-white/6 px-2 py-0.5 rounded-full text-slate-400">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-300 font-medium">{value}</span>
    </span>
  );
}

/** Lazy image with skeleton shimmer + fallback emoji */
function LazyImage({ initialSrc, name }) {
  const [src, setSrc]         = useState(initialSrc || "");
  const [loading, setLoading] = useState(!initialSrc || !initialSrc.startsWith("https://"));
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    if (initialSrc && initialSrc.startsWith("https://")) {
      setSrc(initialSrc);
      setLoading(false);
      return;
    }
    if (!name) { setLoading(false); return; }
    let cancelled = false;
    fetch(apiUrl(`/api/laptop-image?name=${encodeURIComponent(name)}`))
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && d.image_url) {
          setSrc(d.image_url);
        }
        if (!cancelled) setLoading(false);
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [name, initialSrc]);

  if (loading) return <div className="w-full h-40 skeleton" aria-hidden="true" />;

  if (errored || !src) {
    return (
      <div className="w-full h-40 bg-gradient-to-br from-bg-surface to-bg-card flex items-center justify-center text-5xl" aria-hidden="true">
        💻
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={name}
      className="w-full h-40 object-cover bg-bg-surface"
      onError={() => setErrored(true)}
    />
  );
}

export default function RecommendationCard({ laptop, predictedPrice }) {
  const {
    product_id, name, brand, cpu, gpu, ram, storage,
    display, price, seller, in_band, match_score, buy_url, image_url, price_delta,
  } = laptop;

  const colors = scoreColor(match_score);

  // Human-readable delta
  const delta    = price_delta ?? (price - predictedPrice);
  const absDelta = Math.abs(delta);
  const deltaText  = delta === 0
    ? "Exact match"
    : `₹${fmt(absDelta)} ${delta > 0 ? "above" : "below"} target`;
  const deltaClass = delta > 0 ? "text-red-400" : delta < 0 ? "text-green-400" : "text-blue-400";

  return (
    <div className="glass glass-hover flex flex-col overflow-hidden animate-slide-up">
      {/* ── Image + badges ───────────────────────────────────────────────── */}
      <div className="relative">
        <LazyImage initialSrc={image_url} name={name} />

        {/* Match score badge */}
        <div className={`absolute top-3 right-3 text-xs font-bold px-2.5 py-1 rounded-full border ${colors.badge}`}>
          {match_score}% match
        </div>

        {/* In-band badge */}
        {in_band ? (
          <div className="absolute top-3 left-3 text-xs font-medium px-2.5 py-1 rounded-full text-green-400 bg-green-400/10 border border-green-400/20">
            ✓ In your range
          </div>
        ) : (
          <div className="absolute top-3 left-3 text-xs font-medium px-2.5 py-1 rounded-full text-amber-400 bg-amber-400/10 border border-amber-400/20">
            ↗ Outside range
          </div>
        )}
      </div>

      {/* ── Content ──────────────────────────────────────────────────────── */}
      <div className="p-4 flex flex-col gap-3 flex-1">
        <div>
          <h3 className="font-display font-semibold text-white text-sm leading-snug line-clamp-2">{name}</h3>
          <p className="text-xs text-muted mt-0.5">{seller}</p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {ram     && <SpecChip label="RAM"     value={ram} />}
          {storage && <SpecChip label="Storage" value={storage} />}
          {display && <SpecChip label="Display" value={display} />}
          {gpu     && <SpecChip label="GPU"     value={gpu.split(" ").slice(0,3).join(" ")} />}
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted">
            <span>Spec match</span>
            <span className={colors.badge.split(" ")[0]}>{match_score}%</span>
          </div>
          <div className="h-1.5 bg-bg-surface rounded-full overflow-hidden">
            <div
              className={`score-bar-fill bg-gradient-to-r ${colors.bar}`}
              style={{ "--score-width": `${match_score}%` }}
            />
          </div>
        </div>

        <div className="mt-auto pt-4 border-t border-white/5 space-y-3">
          <div className="flex items-end justify-between">
            <p className="font-display font-bold text-xl text-white">₹{fmt(price)}</p>
            <p className={`text-xs font-medium ${deltaClass}`}>{deltaText}</p>
          </div>
          <div className="flex gap-2">
            <a
              href={(!buy_url || buy_url === "nan" || buy_url === "None" || String(buy_url).trim() === "") ? `https://www.flipkart.com/search?q=${encodeURIComponent(name)}` : buy_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-gradient flex-1 py-2.5 rounded-xl font-display font-semibold text-sm flex items-center justify-center gap-1.5 transition-transform hover:scale-[1.02]"
            >
              🛒 Flipkart
            </a>
            <a
              href={`https://www.amazon.in/s?k=${encodeURIComponent(name)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/10 hover:bg-[#FF9900] hover:text-black flex-1 py-2.5 rounded-xl font-display font-semibold text-sm flex items-center justify-center gap-1.5 transition-all duration-300 hover:scale-[1.02]"
            >
              🛒 Amazon
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
