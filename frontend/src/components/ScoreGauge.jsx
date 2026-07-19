import React from "react";
import { bandColor } from "../lib.js";

// Circular score gauge drawn with SVG (no chart library — full control of
// the visual, and it matches the brand). Animates via strokeDashoffset.
export default function ScoreGauge({ value, max = 100, band = "good", label = "Score" }) {
  const size = 168;
  const stroke = 13;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  const offset = circumference * (1 - pct);
  const color = bandColor(band);

  return (
    <div className="gauge">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-3)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(0.2,0.8,0.2,1)" }}
        />
      </svg>
      <div className="num">
        <b>{Math.round(value)}</b>
        <span>{label}</span>
      </div>
    </div>
  );
}
