import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0E12",
        panel: "#10161D",
        panel2: "#151D26",
        border: "#232B34",
        ink: "#E7EDF3",
        muted: "#8492A0",
        signal: "#2DD4C6",
        signalSoft: "#1B8C82",
        warn: "#F5A623",
        crit: "#EF5350",
        ok: "#4ADE80",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
