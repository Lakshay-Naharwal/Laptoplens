/**
 * App.jsx
 * Main application shell for LaptopLens — AI Price Intelligence.
 *
 * Layout:
 *  ┌──────────────────────────────────────────────────┐
 *  │  Navbar                                          │
 *  ├────────────────┬─────────────────────────────────┤
 *  │  SpecForm      │  PredictionResult               │
 *  │                │  (+ Find Laptops CTA)           │
 *  ├────────────────┴─────────────────────────────────┤
 *  │  Recommendation Cards Grid                       │
 *  ├──────────────────────────────────────────────────┤
 *  │  PriceHistoryChart (slide-in panel, conditional) │
 *  └──────────────────────────────────────────────────┘
 */

import { useState, useRef } from "react";
import SpecForm            from "./components/SpecForm";
import PredictionResult    from "./components/PredictionResult";
import RecommendationCard  from "./components/RecommendationCard";
import { CardSkeleton, ResultSkeleton } from "./components/SkeletonLoader";
import { predictPrice, fetchRecommendations } from "./api/client";

export default function App() {
  // ── State ────────────────────────────────────────────────────────────────
  const [predResult,   setPredResult]   = useState(null);
  const [laptops,      setLaptops]      = useState([]);
  const [recSummary,   setRecSummary]   = useState(null); // { in_band_count, total_count, tolerance }

  const [loadingPred,  setLoadingPred]  = useState(false);
  const [loadingRecs,  setLoadingRecs]  = useState(false);
  const [predError,    setPredError]    = useState(null);
  const [recSource,    setRecSource]    = useState(null);   // "mock" | "live"
  const [toast,        setToast]        = useState(null);

  // Ref for recommendation scroll target
  const recsRef = useRef(null);

  // ── Toast helper ─────────────────────────────────────────────────────────
  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  // ── Handlers ─────────────────────────────────────────────────────────────

  /** Called when the form submits (predict + auto-scroll). */
  const handlePredict = async (formData) => {
    setLoadingPred(true);
    setPredError(null);
    setPredResult(null);
    setLaptops([]);

    try {
      const result = await predictPrice(formData);
      setPredResult({ ...result, _formData: formData });
      showToast(`Price predicted: ${result.formatted}`, "success");
    } catch (err) {
      const msg = err.response?.data?.error ?? "Prediction failed. Is Flask running?";
      setPredError(msg);
      showToast(msg, "error");
    } finally {
      setLoadingPred(false);
    }
  };

  /** Called by "Find Matching Laptops" button in PredictionResult, receives tolerance from slider. */
  const handleFindLaptops = async (tolerance) => {
    if (!predResult) return;
    setLoadingRecs(true);
    setLaptops([]);
    setRecSummary(null);

    const { price, _formData } = predResult;
    try {
      const { laptops: list, source, in_band_count, total_count } = await fetchRecommendations({
        predicted_price:  price,
        confidence_band:  tolerance,
        use_case:         _formData.use_case ?? "",
        ram:              _formData.Ram ?? 0,
        gpu_type:         (_formData.GPU || "").toLowerCase().includes("rtx") ||
                          (_formData.GPU || "").toLowerCase().includes("gtx") ||
                          (_formData.GPU || "").toLowerCase().includes("mx")
                            ? "dedicated" : "integrated",
        use_live:         false,
      });
      setLaptops(list);
      setRecSource(source);
      setRecSummary({ in_band_count, total_count, tolerance });
      showToast(`Found ${list.length} laptops — ${in_band_count} in your range`, "success");

      setTimeout(() => {
        recsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    } catch (err) {
      showToast("Could not fetch recommendations.", "error");
    } finally {
      setLoadingRecs(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="relative min-h-screen">
      {/* Aurora background */}
      <div className="aurora-bg" aria-hidden="true">
        <div className="aurora-sphere" />
        <div className="aurora-sphere" />
        <div className="aurora-sphere" />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-8">

        {/* ── Navbar ─────────────────────────────────────────────────────── */}
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-blue to-accent-purple flex items-center justify-center text-lg shadow-glow-blue">
              🔍
            </div>
            <div>
              <h1 className="font-display font-bold text-xl text-white leading-none">
                Laptop<span className="gradient-text">Lens</span>
              </h1>
              <p className="text-xs text-muted leading-none mt-0.5">AI Price Intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted">
            <span className="hidden sm:inline">Powered by XGBoost + Flask</span>
            <span className="px-2 py-1 rounded-full bg-green-400/10 border border-green-400/20 text-green-400 text-xs">
              ● Live
            </span>
          </div>
        </header>

        {/* ── Hero ───────────────────────────────────────────────────────── */}
        <div className="text-center space-y-3 py-4">
          <h2 className="font-display font-extrabold text-4xl sm:text-5xl leading-tight text-white">
            Know the{" "}
            <span className="gradient-text">Fair Price</span>
            <br className="hidden sm:block" /> before you buy
          </h2>
          <p className="text-slate-400 text-base max-w-xl mx-auto text-balance">
            Enter your desired specs and get an AI-predicted fair price range,
            matched with real-time listings and full price history tracking.
          </p>
        </div>

        {/* ── Main two-column layout ─────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Spec form — wider */}
          <div className="lg:col-span-3">
            <SpecForm onPredict={handlePredict} isLoading={loadingPred} />
            {predError && (
              <p className="mt-3 text-red-400 text-sm text-center">{predError}</p>
            )}
          </div>

          {/* Prediction result — narrower */}
          <div className="lg:col-span-2">
            {loadingPred ? (
              <ResultSkeleton />
            ) : (
              <PredictionResult
                result={predResult}
                onFindLaptops={handleFindLaptops}
                isLoadingRecs={loadingRecs}
              />
            )}
          </div>
        </div>

        {/* ── Recommendation grid ────────────────────────────────────────── */}
        {(loadingRecs || laptops.length > 0) && (
          <section ref={recsRef} className="space-y-5">
          <div className="flex items-center justify-between">
              <h2 className="font-display font-bold text-2xl text-white">
                Matching Laptops
              </h2>
              <div className="flex items-center gap-3">
                {recSummary && (
                  <span className="text-sm text-slate-300">
                    <span className="text-green-400 font-semibold">{recSummary.in_band_count}</span>
                    <span className="text-slate-500"> of </span>
                    <span className="font-semibold">{recSummary.total_count}</span>
                    <span className="text-slate-500"> within ±₹{recSummary.tolerance?.toLocaleString("en-IN")}</span>
                  </span>
                )}
                {recSource && (
                  <span className="text-xs text-muted px-3 py-1 rounded-full bg-bg-surface border border-white/6">
                    {recSource === "live" ? "🔴 Live data"
                     : recSource === "real" ? "🟢 Real listings"
                     : "📝 Demo data"}
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
              {loadingRecs
                ? [...Array(6)].map((_, i) => <CardSkeleton key={i} />)
                : laptops.map((laptop) => (
                    <RecommendationCard
                      key={laptop.product_id}
                      laptop={laptop}
                      predictedPrice={predResult?.price ?? 0}
                    />
                  ))
              }
            </div>
          </section>
        )}

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <footer className="text-center text-xs text-slate-700 pb-6 space-y-1">
          <p>LaptopLens · Built with Flask + XGBoost + React · Deployed on Hugging Face Spaces</p>
          <p>Price predictions are estimates based on historical data. Always verify before purchasing.</p>
        </footer>
      </div>

      {/* ── Toast notification ─────────────────────────────────────────── */}
      {toast && (
        <div
          className={`
            fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-medium shadow-card
            flex items-center gap-2 animate-slide-up
            ${toast.type === "success" ? "bg-green-500/20 border border-green-500/30 text-green-300"
              : toast.type === "error" ? "bg-red-500/20 border border-red-500/30 text-red-300"
              : "bg-bg-card border border-white/8 text-white"}
          `}
        >
          {toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}
          {toast.msg}
        </div>
      )}
    </div>
  );
}
