import React, { useState } from "react";
import {
  getInterviewQuestions,
  buildResume,
  downloadResume,
  profileFromAnalysis,
} from "../api.js";

/**
 * The gap-fill interview.
 *
 * Three stages, driven by local state:
 *   idle      → a call-to-action under the score report
 *   answering → the generated questions, one card each
 *   done      → the rebuilt resume, its new score, and download buttons
 */
export default function InterviewPanel({ report, filename }) {
  const [stage, setStage] = useState("idle");
  const [engine, setEngine] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyFormat, setBusyFormat] = useState("");
  const [savedProfile, setSavedProfile] = useState("");

  const answeredCount = questions.filter((q) => (answers[q.id] || "").trim()).length;
  const requiredLeft = questions.filter(
    (q) => !q.optional && !(answers[q.id] || "").trim()
  ).length;

  async function start() {
    setLoading(true);
    setError("");
    try {
      const res = await getInterviewQuestions(report.id);
      setQuestions(res.questions || []);
      setEngine(res.engine || "");
      setStage(res.questions?.length ? "answering" : "clean");
    } catch (e) {
      setError(e.message || "Couldn't generate questions.");
    } finally {
      setLoading(false);
    }
  }

  async function submit() {
    setLoading(true);
    setError("");
    try {
      const res = await buildResume(report.id, answers);
      setResult(res);
      setStage("done");
    } catch (e) {
      setError(e.message || "Couldn't rebuild the resume.");
    } finally {
      setLoading(false);
    }
  }

  async function save(format) {
    setBusyFormat(format);
    setError("");
    try {
      const stem = (filename || "resume").replace(/\.[^.]+$/, "");
      await downloadResume(result.resume_text, format, `${stem}-radar`);
    } catch (e) {
      setError(e.message || "Download failed.");
    } finally {
      setBusyFormat("");
    }
  }

  async function saveAsProfile() {
    setBusyFormat("profile");
    setError("");
    try {
      const res = await profileFromAnalysis(report.id);
      setSavedProfile(
        res.usable
          ? "Saved to your profile — the Applications tab can now tailor resumes from it."
          : "Saved, but some fields came through blank. Check the Profile tab and fill them in."
      );
    } catch (e) {
      setError(e.message || "Couldn't save that to your profile.");
    } finally {
      setBusyFormat("");
    }
  }

  function reset() {
    setStage("idle");
    setQuestions([]);
    setAnswers({});
    setResult(null);
    setError("");
  }

  // ---------------------------------------------------------------- idle
  if (stage === "idle") {
    return (
      <div className="card pad-lg fade-in" style={{ marginTop: 22 }}>
        <div className="section-title">Rebuild this resume with me</div>
        <p className="muted" style={{ marginTop: 6, maxWidth: "62ch" }}>
          RADAR knows exactly which facts are missing from your resume. Answer a short set of
          targeted questions and it will write those answers back in, then re-score the result.
        </p>
        {error && <div className="banner error" style={{ marginTop: 14 }}>{error}</div>}
        <button className="btn primary" style={{ marginTop: 16 }} onClick={start} disabled={loading}>
          {loading && <span className="spinner" />}
          {loading ? "Finding the gaps…" : "Start the interview"}
        </button>
      </div>
    );
  }

  // --------------------------------------------------------------- clean
  if (stage === "clean") {
    return (
      <div className="card pad-lg fade-in" style={{ marginTop: 22 }}>
        <div className="section-title">Nothing left to ask</div>
        <p className="muted" style={{ marginTop: 6 }}>
          RADAR found no blocking gaps in this resume — contact details, sections and metrics are
          all present. Use the Rewrite tab to polish individual lines.
        </p>
      </div>
    );
  }

  // ----------------------------------------------------------- answering
  if (stage === "answering") {
    return (
      <div className="card pad-lg fade-in" style={{ marginTop: 22 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <div>
            <div className="section-title">A few questions</div>
            <div className="muted">
              {questions.length} gap{questions.length === 1 ? "" : "s"} found · questions written by{" "}
              {engine === "gemini" ? "Gemini" : "the offline engine"}
            </div>
          </div>
          <span className="pill">
            {answeredCount}/{questions.length} answered
          </span>
        </div>

        {error && <div className="banner error" style={{ marginTop: 16 }}>{error}</div>}

        <div style={{ marginTop: 18 }}>
          {questions.map((q, i) => (
            <div key={q.id} className="fix" style={{ display: "block", paddingTop: 18 }}>
              <div className="area">
                {q.area}
                {q.optional && <span style={{ opacity: 0.6 }}> · optional</span>}
              </div>
              <div className="txt" style={{ marginTop: 4, marginBottom: 8 }}>
                <b style={{ color: "var(--accent)" }}>{i + 1}.</b> {q.question}
              </div>
              {q.kind === "long" ? (
                <textarea
                  placeholder={q.hint}
                  value={answers[q.id] || ""}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                />
              ) : (
                <input
                  type="text"
                  placeholder={q.hint}
                  value={answers[q.id] || ""}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                />
              )}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <button className="btn primary" onClick={submit} disabled={loading || answeredCount === 0}>
            {loading && <span className="spinner" />}
            {loading ? "Rebuilding…" : "Rebuild my resume"}
          </button>
          <button className="btn ghost" onClick={reset} disabled={loading}>
            Cancel
          </button>
          {requiredLeft > 0 && (
            <span className="muted">
              {requiredLeft} important question{requiredLeft === 1 ? "" : "s"} still blank — you can
              still continue.
            </span>
          )}
        </div>
      </div>
    );
  }

  // ----------------------------------------------------------------- done
  const delta = (result.score_after ?? 0) - (result.score_before ?? 0);
  return (
    <div className="card pad-lg fade-in" style={{ marginTop: 22 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div className="section-title">Your rebuilt resume</div>
          <div className="muted">
            Written by {result.engine === "gemini" ? "Gemini" : "the offline rule engine"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span className="pill">Before {result.score_before}</span>
          <span className="pill">After {result.score_after}</span>
          <span
            className="grade-badge"
            style={{
              background: delta >= 0 ? "rgba(53,196,107,0.12)" : "rgba(224,86,86,0.1)",
              color: delta >= 0 ? "var(--good)" : "var(--critical)",
            }}
          >
            {delta >= 0 ? `+${delta}` : delta} pts
          </span>
        </div>
      </div>

      {error && <div className="banner error" style={{ marginTop: 16 }}>{error}</div>}

      {delta <= 0 && (
        <div className="banner info" style={{ marginTop: 16 }}>
          The score didn't move much. That usually means the answers added detail rather than the
          specific signals the rubric measures — check the fixes list and try again with numbers.
        </div>
      )}

      <pre
        style={{
          marginTop: 18,
          padding: 18,
          background: "var(--surface-2)",
          border: "1px solid var(--border-soft)",
          borderRadius: "var(--radius-sm)",
          whiteSpace: "pre-wrap",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 13,
          lineHeight: 1.6,
          maxHeight: 460,
          overflowY: "auto",
        }}
      >
        {result.resume_text}
      </pre>

      <div style={{ marginTop: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button className="btn primary" onClick={() => save("docx")} disabled={!!busyFormat}>
          {busyFormat === "docx" && <span className="spinner" />}
          Download .docx
        </button>
        <button className="btn ghost" onClick={() => save("pdf")} disabled={!!busyFormat}>
          {busyFormat === "pdf" && <span className="spinner" />}
          Download .pdf
        </button>
        <button
          className="btn ghost"
          onClick={() => navigator.clipboard?.writeText(result.resume_text)}
        >
          Copy text
        </button>
        <button className="btn ghost" onClick={saveAsProfile} disabled={!!busyFormat}>
          {busyFormat === "profile" && <span className="spinner" />}
          Save as my profile
        </button>
        <button className="btn ghost" onClick={reset}>
          Start over
        </button>
      </div>

      {savedProfile && (
        <div className="banner info" style={{ marginTop: 16, marginBottom: 0 }}>
          {savedProfile}
        </div>
      )}

      {result.changes?.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <div className="section-title" style={{ fontSize: 16 }}>
            What changed
          </div>
          {result.changes.map((c, i) => (
            <div key={i} className="fix">
              <div className="idx">{i + 1}</div>
              <div>
                <div className="area">{c.area}</div>
                {c.before ? (
                  <div className="txt" style={{ marginTop: 4 }}>
                    <div style={{ opacity: 0.55, textDecoration: "line-through" }}>{c.before}</div>
                    <div style={{ color: "var(--good)", marginTop: 3 }}>{c.after}</div>
                  </div>
                ) : (
                  <div className="txt">{c.text}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
