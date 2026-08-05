import React, { useEffect, useState } from "react";
import { getSummary } from "../api.js";

const STAGES = ["Saved", "Applied", "Interviewing", "Offer", "Rejected"];

/**
 * The landing page.
 *
 * Answers one question — what should I do next? — before anything else. The
 * follow-up list comes first for that reason; the counts are context, not the
 * point. Every number here is computed by the backend from the same urgency
 * rule the tracker cards use, so the two can never disagree.
 */
export default function DashboardView({ onNavigate, userName }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getSummary()
      .then(setData)
      .catch((e) => setError(e.message || "Couldn't load your dashboard."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty">Loading…</div>;
  if (error) return <div className="banner error">{error}</div>;

  const t = data.totals;
  const isEmpty = t.applications === 0 && t.analyses === 0;
  const firstName = (userName || "").trim().split(/\s+/)[0];

  return (
    <div className="fade-in">
      <div className="page-head">
        <div className="eyebrow">Dashboard</div>
        <h1>{firstName ? `Welcome back, ${firstName}` : "Your search at a glance"}</h1>
        <p>
          {isEmpty
            ? "Nothing here yet. Score a resume or add a job posting and this fills in."
            : "What needs your attention, and how the search is going."}
        </p>
      </div>

      {isEmpty ? (
        <div className="card pad-lg">
          <div className="section-title">Start here</div>
          <div className="muted" style={{ marginBottom: 18 }}>
            Two ways in — score a resume you already have, or file a job you want to go for.
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="btn primary" onClick={() => onNavigate("analyze")}>
              Score a resume
            </button>
            <button className="btn ghost" onClick={() => onNavigate("tracker")}>
              Add a job posting
            </button>
          </div>
        </div>
      ) : (
        <>
          {t.needs_follow_up > 0 && (
            <div className="card pad-lg" style={{ marginBottom: 20 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                <div className="section-title" style={{ margin: 0 }}>
                  Needs chasing
                </div>
                <button className="link-btn" onClick={() => onNavigate("tracker")}>
                  Open the tracker
                </button>
              </div>
              <div className="muted" style={{ marginTop: 4, marginBottom: 14 }}>
                {t.needs_follow_up === 1
                  ? "One application has gone quiet or is closing soon."
                  : `${t.needs_follow_up} applications have gone quiet or are closing soon.`}
              </div>

              <div style={{ display: "grid", gap: 10 }}>
                {data.follow_ups.map((a) => (
                  <div
                    key={a.id}
                    className={`card edge edge-${a.urgency.level}`}
                    style={{ padding: "12px 16px", boxShadow: "none" }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 12,
                        alignItems: "center",
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 14.5 }}>
                          {a.title || "Untitled role"}
                        </div>
                        <div className="muted" style={{ fontSize: 13 }}>
                          {a.company || "Unknown company"}
                        </div>
                      </div>
                      <span className={`urg urg-${a.urgency.level}`}>{a.urgency.label}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid cols-2" style={{ gap: 20 }}>
            <div className="card pad-lg">
              <div className="section-title">Pipeline</div>
              <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
                {STAGES.map((stage) => {
                  const n = data.by_status[stage] || 0;
                  const share = t.applications ? Math.round((n / t.applications) * 100) : 0;
                  return (
                    <div key={stage}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: 13.5,
                          marginBottom: 4,
                        }}
                      >
                        <span className={n ? "" : "muted"}>{stage}</span>
                        <span className={n ? "" : "muted"}>{n}</span>
                      </div>
                      <div className="track" style={{ height: 6, margin: 0 }}>
                        <i
                          style={{
                            width: `${share}%`,
                            background: n ? "var(--accent)" : "transparent",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card pad-lg">
              <div className="section-title">Totals</div>
              <div style={{ display: "grid", gap: 12, marginTop: 4 }}>
                <Stat label="Applications tracked" value={t.applications} />
                <Stat label="Companies that replied" value={t.replied} />
                <Stat label="Tailored resumes built" value={t.with_resume} />
                <Stat label="Resumes scored" value={t.analyses} />
                {data.best_score != null && (
                  <Stat label="Best score" value={`${data.best_score}/100`} />
                )}
              </div>
              <div style={{ marginTop: 18, display: "flex", gap: 10, flexWrap: "wrap" }}>
                <button className="btn ghost" onClick={() => onNavigate("tracker")}>
                  Tracker
                </button>
                <button className="btn ghost" onClick={() => onNavigate("analyze")}>
                  Score a resume
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
      <span className="muted" style={{ fontSize: 13.5 }}>
        {label}
      </span>
      <span style={{ fontFamily: "var(--serif)", fontSize: 20, fontWeight: 600 }}>{value}</span>
    </div>
  );
}
