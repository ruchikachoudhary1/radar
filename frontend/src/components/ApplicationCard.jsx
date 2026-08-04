import React from "react";

// Colour the stage so the pipeline is readable at a glance.
const STATUS_TONE = {
  Saved: { bg: "var(--surface-3)", fg: "var(--ink-2)" },
  Applied: { bg: "var(--accent-dim)", fg: "var(--accent-2)" },
  Interviewing: { bg: "rgba(232,184,75,0.18)", fg: "var(--accent-2)" },
  Offer: { bg: "rgba(53,196,107,0.12)", fg: "var(--good)" },
  Rejected: { bg: "rgba(224,86,86,0.1)", fg: "var(--critical)" },
};

export default function ApplicationCard({ app, statuses, onMove, onDelete, onView }) {
  const tone = STATUS_TONE[app.status] || STATUS_TONE.Saved;
  // The list query returns a computed has_resume flag; a freshly created record
  // comes back as the full row instead, carrying resume_text itself.
  const hasResume = Boolean(app.has_resume || app.resume_text);
  const facts = [app.job_type, app.work_mode, app.location, app.stipend, app.duration].filter(
    Boolean
  );

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 14,
          alignItems: "flex-start",
          flexWrap: "wrap",
        }}
      >
        <div style={{ minWidth: 0, flex: "1 1 260px" }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>{app.title || "Untitled role"}</div>
          <div className="muted" style={{ marginTop: 2 }}>
            {app.company || "Unknown company"}
            {app.url && (
              <>
                {" · "}
                <a
                  href={app.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "var(--accent-2)" }}
                >
                  posting
                </a>
              </>
            )}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {app.match_score != null && <span className="pill">{app.match_score}% match</span>}
          <span
            className="grade-badge"
            style={{ background: tone.bg, color: tone.fg, fontSize: 13 }}
          >
            {app.status}
          </span>
        </div>
      </div>

      {facts.length > 0 && (
        <div className="chips">
          {facts.map((fact, i) => (
            <span className="chip" key={i}>
              {fact}
            </span>
          ))}
        </div>
      )}

      {app.notes && (
        <div className="muted" style={{ marginTop: 12, fontSize: 13.5 }}>
          {app.notes}
        </div>
      )}

      <div
        style={{
          marginTop: 16,
          display: "flex",
          gap: 10,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="muted">Stage</span>
          <select
            value={app.status}
            onChange={(e) => onMove(app.id, e.target.value)}
            style={{ width: "auto", padding: "8px 12px" }}
          >
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <button className="btn ghost" onClick={() => onView(app.id)} style={{ padding: "9px 16px" }}>
          {hasResume ? "View resume" : "Build resume"}
        </button>

        <button
          className="link-btn"
          style={{ color: "var(--critical)", marginLeft: "auto" }}
          onClick={() => {
            if (window.confirm(`Remove ${app.title || "this application"} from the tracker?`)) {
              onDelete(app.id);
            }
          }}
        >
          Remove
        </button>
      </div>
    </div>
  );
}
