import React from "react";

/**
 * Placeholder blocks shown while a view loads.
 *
 * Reserving the space content will occupy stops the layout jumping when the
 * data arrives. The blocks are hidden from assistive technology — a screen
 * reader gets the live status message instead of a description of grey boxes.
 */
export default function Skeleton({ rows = 3, label = "Loading" }) {
  return (
    <div className="fade-in">
      <span className="sr-only" role="status" aria-live="polite">
        {label}
      </span>
      <div aria-hidden="true" style={{ display: "grid", gap: 14, marginTop: 20 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div className="card" key={i}>
            <div className="skel skel-line" style={{ width: "42%", height: 16 }} />
            <div className="skel skel-line" style={{ width: "68%" }} />
            <div className="skel skel-line" style={{ width: "55%", marginBottom: 0 }} />
          </div>
        ))}
      </div>
    </div>
  );
}
