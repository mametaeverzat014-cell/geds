import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-base":     "#07090C",
        "bg-elevated": "#0E1116",
        "bg-glass":    "rgba(14, 17, 22, 0.65)",
        "border-subtle": "#1A1E26",
        "border-strong": "#2A3140",
        "text-primary":   "#E6EBF4",
        "text-secondary": "#99A4B5",
        "text-muted":     "#5B6473",
        "accent-cyan":   "#4DD0E1",
        "accent-violet": "#7C6CFB",
        "accent-gold":   "#FFC34D",
        "sev-1": "#2DD4BF",
        "sev-2": "#67D6A4",
        "sev-3": "#FFC34D",
        "sev-4": "#F97316",
        "sev-5": "#EF4444",
      },
      fontFamily: {
        display: ["Manrope", "ui-sans-serif", "system-ui"],
        mono:    ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
