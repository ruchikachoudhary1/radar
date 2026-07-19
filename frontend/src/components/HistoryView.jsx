import React, { useEffect, useState } from "react";
import { getHistory } from "../api.js";
import { gradeColor, formatDate } from "../lib.js";

export default function HistoryView() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getHistory()
      .then((res) => setItems(res.items))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">History</div>
        <h1>Past analyses</h1>
        <p>Every resume you score is saved to the database so you can track progress over time.</p>
      </div>

      {error && <div className="banner error">{error}</div>}

      <div className="card pad-lg">
        {items === null && <div className="empty">Loading…</div>}
        {items && items.length === 0 && (
          <div className="empty">No analyses yet — score a resume to see it here.</div>
        )}
        {items &&
          items.map((it) => (
            <div className="hist-row" key={it.id}>
              <div>
                <div className="hist-file">{it.filename}</div>
                <div className="hist-meta">
                  {it.role || "No target role"} · {formatDate(it.created_at)}
                </div>
              </div>
              <span className="pill">{it.role ? "role" : "general"}</span>
              <span
                className="grade-badge"
                style={{ background: "var(--surface-3)", color: gradeColor(it.grade) }}
              >
                {it.grade}
              </span>
              <span className="dim-score" style={{ minWidth: 54, textAlign: "right" }}>
                {it.overall}
                <span style={{ color: "var(--ink-3)" }}> /100</span>
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}
