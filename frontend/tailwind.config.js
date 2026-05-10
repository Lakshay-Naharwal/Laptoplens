/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "system-ui", "sans-serif"],
      },
      colors: {
        // Design system tokens
        bg: {
          base:    "#080e1a",
          surface: "#0f1929",
          card:    "#111d2e",
          hover:   "#162236",
        },
        accent: {
          blue:    "#3b82f6",
          purple:  "#8b5cf6",
          cyan:    "#22d3ee",
          pink:    "#ec4899",
          green:   "#10b981",
          amber:   "#f59e0b",
        },
        muted: "#64748b",
      },
      backgroundImage: {
        "gradient-aurora":  "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%)",
        "gradient-card":    "linear-gradient(145deg, rgba(17,29,46,0.9), rgba(8,14,26,0.95))",
      },
      boxShadow: {
        "glow-blue":   "0 0 20px rgba(59,130,246,0.3)",
        "glow-purple": "0 0 20px rgba(139,92,246,0.3)",
        "card":        "0 4px 24px rgba(0,0,0,0.4)",
        "card-hover":  "0 8px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(59,130,246,0.15)",
      },
      animation: {
        "float":        "float 8s ease-in-out infinite alternate",
        "pulse-slow":   "pulse 4s cubic-bezier(0.4,0,0.6,1) infinite",
        "slide-up":     "slideUp 0.4s ease-out",
        "fade-in":      "fadeIn 0.3s ease-out",
        "shimmer":      "shimmer 1.5s infinite",
        "score-fill":   "scoreFill 1s ease-out forwards",
      },
      keyframes: {
        float:     { "0%": { transform: "translateY(0) scale(1)" }, "100%": { transform: "translateY(-20px) scale(1.05)" } },
        slideUp:   { "0%": { opacity: 0, transform: "translateY(20px)" }, "100%": { opacity: 1, transform: "translateY(0)" } },
        fadeIn:    { "0%": { opacity: 0 }, "100%": { opacity: 1 } },
        shimmer:   { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
        scoreFill: { "0%": { width: "0%" }, "100%": { width: "var(--score-width)" } },
      },
    },
  },
  plugins: [],
};
