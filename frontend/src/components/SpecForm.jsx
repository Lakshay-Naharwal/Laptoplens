/**
 * components/SpecForm.jsx
 * Specification input form with:
 *  - Dropdowns for categorical model features (brand, processor, RAM type, etc.)
 *  - Number inputs for numerical features (display size, ROM, etc.)
 *  - Use-case tag pill selector (Gaming / Office / Design / Programming / General)
 *  - User-adjustable confidence band slider
 */

import { useState, useEffect } from "react";
import { fetchMetadata } from "../api/client";

// Map raw model column names to user-friendly labels
const LABEL_MAP = {
  brand: "Brand",
  processor: "Processor",
  Ram_type: "RAM Type",
  ROM_type: "Storage Type",
  GPU: "GPU",
  OS: "Operating System",
  Ram: "RAM (GB)",
  ROM: "Storage (GB)",
  display_size: "Display Size (inches)",
  resolution_width: "Resolution Width (px)",
  resolution_height: "Resolution Height (px)",
  warranty: "Warranty (years)",
};

// Columns that should never be shown in the form (computed/scraped fields)
const HIDDEN_COLS = new Set(["spec_rating"]);

const PLACEHOLDER_MAP = {
  Ram: "e.g. 16",
  ROM: "e.g. 512",
  display_size: "e.g. 15.6",
  resolution_width: "e.g. 1920",
  resolution_height: "e.g. 1080",
  warranty: "e.g. 1",
};

const USE_CASES = [
  { id: "Gaming",      icon: "🎮", color: "from-red-500 to-orange-500" },
  { id: "Office",      icon: "💼", color: "from-blue-500 to-cyan-500" },
  { id: "Design",      icon: "🎨", color: "from-purple-500 to-pink-500" },
  { id: "Programming", icon: "💻", color: "from-green-500 to-teal-500" },
  { id: "General",     icon: "🌐", color: "from-slate-500 to-slate-400" },
];

const getFilteredOptions = (col, options, useCase) => {
  if (!useCase || useCase === "General" || !options) return options || [];

  if (col === "GPU") {
    const isDedicated = (o) => /rtx|gtx|rx |geforce|radeon pro/i.test(o);
    const isApple = (o) => /m1|m2|m3|core gpu/i.test(o);
    
    if (useCase === "Office") {
      // Exclude dedicated GPUs
      return options.filter(o => !isDedicated(o));
    }
    if (useCase === "Gaming") {
      // Only dedicated GPUs
      return options.filter(o => isDedicated(o));
    }
    if (useCase === "Design") {
      // Dedicated or Apple M-series
      return options.filter(o => isDedicated(o) || isApple(o));
    }
  }

  if (col === "processor") {
    if (useCase === "Programming") {
      // Exclude entry level
      const isEntryLevel = (o) => /i3|ryzen 3|celeron|pentium|athlon/i.test(o);
      return options.filter(o => !isEntryLevel(o));
    }
  }

  return options;
};

const getMinVal = (col, useCase) => {
  if (col === "Ram" && ["Gaming", "Design", "Programming"].includes(useCase)) return 16;
  return 0; // default min
};

export default function SpecForm({ onPredict, isLoading }) {
  const [metadata, setMetadata]   = useState(null);
  const [metaError, setMetaError] = useState(null);
  const [values, setValues]       = useState({});
  const [useCase, setUseCase]     = useState("");
  const [mae, setMae]             = useState(5000);

  // ── Load metadata (form options + model MAE) ──────────────────────────────
  useEffect(() => {
    fetchMetadata()
      .then((data) => {
        setMetadata(data);
        setMae(data.mae ?? 5000);
      })
      .catch((err) => {
        setMetaError("Could not load form options. Is the Flask server running?");
        console.error(err);
      });
  }, []);

  // ── Auto-correct selections on Use Case change ────────────────────────────
  useEffect(() => {
    if (!metadata) return;
    setValues((prev) => {
      let newVals = { ...prev };
      let changed = false;

      // Check categorical
      metadata.categorical_cols.forEach((col) => {
        if (prev[col]) {
          const allowed = getFilteredOptions(col, metadata.categories[col], useCase);
          if (!allowed.includes(prev[col])) {
            newVals[col] = "";
            changed = true;
          }
        }
      });

      // Check numerical min limits
      metadata.numerical_cols.forEach((col) => {
        if (prev[col]) {
          const minReq = getMinVal(col, useCase);
          if (Number(prev[col]) < minReq) {
            newVals[col] = minReq.toString();
            changed = true;
          }
        }
      });

      return changed ? newVals : prev;
    });
  }, [useCase, metadata]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleChange = (col, val) => setValues((prev) => ({ ...prev, [col]: val }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = {
      ...values,
      use_case:        useCase,
      confidence_band: mae,   // use model MAE as default band for prediction
    };
    onPredict(payload);
  };

  // ── Render helpers ────────────────────────────────────────────────────────
  if (metaError) {
    return (
      <div className="glass p-6 text-center">
        <p className="text-red-400 text-sm">{metaError}</p>
        <p className="text-muted text-xs mt-2">Make sure Flask is running on port 5000</p>
      </div>
    );
  }

  if (!metadata) {
    return (
      <div className="glass p-6 space-y-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="skeleton h-12 w-full" />
        ))}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="glass p-6 space-y-6 animate-slide-up">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div>
        <h2 className="font-display text-xl font-bold text-white">
          Laptop Specifications
        </h2>
        <p className="text-muted text-sm mt-1">
          Fill in the specs and set your price tolerance
        </p>
      </div>

      {/* ── Use-case pills ────────────────────────────────────────────────── */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
          Use Case
        </label>
        <div className="flex flex-wrap gap-2">
          {USE_CASES.map((uc) => (
            <button
              key={uc.id}
              type="button"
              onClick={() => setUseCase(useCase === uc.id ? "" : uc.id)}
              className={`
                px-4 py-1.5 rounded-full text-sm font-medium border transition-all duration-200
                ${useCase === uc.id
                  ? `bg-gradient-to-r ${uc.color} text-white border-transparent shadow-md scale-105`
                  : "bg-bg-surface border-white/10 text-slate-400 hover:border-white/20 hover:text-white"
                }
              `}
            >
              {uc.icon} {uc.id}
            </button>
          ))}
        </div>
      </div>

      {/* ── Categorical dropdowns ─────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {metadata.categorical_cols.map((col) => {
          const options = getFilteredOptions(col, metadata.categories[col], useCase);
          return (
          <div key={col} className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
              {LABEL_MAP[col] || col}
            </label>
            <div className="relative">
              <select
                id={col}
                value={values[col] || ""}
                onChange={(e) => handleChange(col, e.target.value)}
                required
                className="
                  w-full bg-bg-surface border border-white/8 rounded-xl
                  px-4 py-2.5 text-sm text-white appearance-none
                  focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/30
                  transition-all duration-200 cursor-pointer
                "
              >
                <option value="" disabled>
                  Select {LABEL_MAP[col] || col}
                </option>
                {options.map((opt) => (
                  <option key={opt} value={opt} className="bg-bg-surface">
                    {opt}
                  </option>
                ))}
              </select>
              {/* Chevron icon */}
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted text-xs">
                ▾
              </span>
            </div>
          </div>
        );
        })}
      </div>

      {/* ── Numerical inputs ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {metadata.numerical_cols.filter(col => !HIDDEN_COLS.has(col)).map((col) => {
          const minReq = getMinVal(col, useCase);
          return (
          <div key={col} className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-widest">
              {LABEL_MAP[col] || col} {minReq > 0 && <span className="text-accent-blue lowercase ml-1">(min {minReq})</span>}
            </label>
            <input
              id={col}
              type="number"
              step="any"
              min={minReq}
              value={values[col] || ""}
              onChange={(e) => handleChange(col, e.target.value)}
              placeholder={PLACEHOLDER_MAP[col] || "Enter value"}
              required
              className="
                w-full bg-bg-surface border border-white/8 rounded-xl
                px-4 py-2.5 text-sm text-white
                focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/30
                transition-all duration-200
                placeholder:text-slate-600
              "
            />
          </div>
        );
        })}
      </div>

      {/* ── Submit ────────────────────────────────────────────────────────── */}
      <button
        type="submit"
        disabled={isLoading}
        className="btn-gradient w-full py-3.5 rounded-xl font-display font-semibold text-base flex items-center justify-center gap-3"
      >
        {isLoading ? (
          <>
            <Spinner />
            Analysing…
          </>
        ) : (
          <>
            <span>✨</span>
            Predict Price
          </>
        )}
      </button>
    </form>
  );
}

function Spinner() {
  return (
    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
  );
}
