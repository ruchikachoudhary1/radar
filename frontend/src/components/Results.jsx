import React from "react";
import ScoreGauge from "./ScoreGauge.jsx";
import { bandColor, gradeColor } from "../lib.js";

function DimensionBar({ d }) {
  const pct = (d.points / d.max) * 100;
  return (
    <div className="dim">
      <div className="dim-top">
        <span className="dim-name">{d.label}</span>
        <span className="dim-score">
          {d.points}
          <span style={{ color: "var(--ink-3)" }}> / {d.max}</span>
        </span>
      </div>
      <div className="track">
        <i style={{ width: `${pct}%`, background: bandColor(d.band) }} />
      </div>
      <div className="dim-detail">{d.detail}</div>
    </div>
  );
}

function Chips({ items, kind, limit = 40 }) {
  if (!items || !items.length) return <span className="muted">None</span>;
  return (
    <div className="chips">
      {items.slice(0, limit).map((k) => (
        <span key={k} className={`chip ${kind}`}>
          {k}
        </span>
      ))}
    </div>
  );
}

export default function Results({ report }) {
  const roleDim = report.dimensions.find((d) => d.key === "role_match");
  const jd = report.jd_match || {};
  const hasJD = jd.score !== null && jd.score !== undefined;

  return (
    <div className="fade-in grid results-area" style={{ gap: 20 }}>
      <div className="results-toolbar no-print" style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn ghost" onClick={() => window.print()}>
          Export report (PDF)
        </button>
      </div>
      <div className="grid cols-2-1">
        {/* Overall score */}
        <div className="card pad-lg">
          <div className="gauge-wrap">
            <ScoreGauge value={report.overall} max={report.overall_max} band={report.band} label="out of 100" />
            <div>
              <span
                className="grade-badge"
                style={{ background: "var(--surface-3)", color: gradeColor(report.grade) }}
              >
                Grade {report.grade}
              </span>
              <h2 style={{ fontSize: 22, marginTop: 12 }}>{report.verdict}</h2>
              <p className="muted" style={{ marginTop: 8 }}>
                {report.meta?.filename} · {report.meta?.word_count} words ·{" "}
                {report.meta?.gemini ? "Gemini AI on" : "rule-based engine"}
              </p>
            </div>
          </div>
        </div>

        {/* Top fixes */}
        <div className="card">
          <div className="section-title">Priority fixes</div>
          <p className="muted" style={{ marginBottom: 6 }}>Ranked by impact on your score.</p>
          {report.top_fixes.length === 0 && <p className="muted">No major issues — nice work.</p>}
          {report.top_fixes.map((f, i) => (
            <div className="fix" key={i}>
              <span className="idx">{i + 1}</span>
              <div>
                <div className="area">{f.area}</div>
                <div className="txt">{f.text}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dimension breakdown */}
      <div className="card pad-lg">
        <div className="section-title">Score breakdown</div>
        <p className="muted" style={{ marginBottom: 8 }}>Six weighted dimensions, summing to 100.</p>
        {report.dimensions.map((d) => (
          <DimensionBar key={d.key} d={d} />
        ))}
      </div>

      {/* Keyword match */}
      {roleDim && (roleDim.matched?.length || roleDim.missing?.length) ? (
        <div className="grid cols-2">
          <div className="card">
            <div className="section-title" style={{ color: "var(--good)" }}>
              Matched keywords ({roleDim.matched.length})
            </div>
            <Chips items={roleDim.matched} kind="on" />
          </div>
          <div className="card">
            <div className="section-title" style={{ color: "var(--critical)" }}>
              Missing keywords ({roleDim.missing.length})
            </div>
            <Chips items={roleDim.missing} kind="off" />
          </div>
        </div>
      ) : null}

      {/* JD match */}
      {hasJD && (
        <div className="card pad-lg">
          <div className="gauge-wrap" style={{ marginBottom: 14 }}>
            <ScoreGauge value={jd.score} max={100} band={jd.score >= 70 ? "good" : jd.score >= 45 ? "warning" : "critical"} label="JD coverage" />
            <div>
              <div className="section-title">Job-description fit</div>
              <p className="muted" style={{ maxWidth: "46ch" }}>
                {jd.score}% of the job description's key terms appear in your resume.
                TF-IDF similarity: {jd.similarity}%.
              </p>
              <div style={{ marginTop: 12 }}>
                <div className="field-label" style={{ color: "var(--critical)" }}>
                  Missing from your resume
                </div>
                <Chips items={jd.missing} kind="off" limit={16} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
