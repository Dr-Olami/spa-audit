import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"]
      },
      colors: {
        brand: {
          50: "#fff1f5",
          100: "#ffe4ec",
          200: "#ffc9da",
          300: "#ff9dbd",
          400: "#ff6298",
          500: "#ff2e7a",
          600: "#ee0e63",
          700: "#c80052",
          800: "#a50448",
          900: "#880941",
          950: "#4d0021"
        },
        ink: {
          50: "#f6f6f7",
          100: "#e7e7ea",
          900: "#0b0b10",
          950: "#06060a"
        }
      },
      boxShadow: {
        glow: "0 10px 40px -10px rgba(255, 46, 122, 0.55)"
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px)"
      },
      animation: {
        "fade-up": "fadeUp 0.6s ease-out both",
        "pulse-slow": "pulse 3s ease-in-out infinite"
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      }
    }
  },
  plugins: []
};

export default config;
