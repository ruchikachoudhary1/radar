import React, { useRef, useState } from "react";
import { analyzeResume } from "../api.js";
import Results from "./Results.jsx";

export default function AnalyzeView({ roles }) {
  const [file, setFile] = useState(null);
  const [role, setRole] = useState("");
  const [jd, setJd] = useState("");
  const [showJd, setShowJd] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const inputRef = useRef(null);

  function pick(f) {
    if (!f) return;
    setFile(f);
    setError("");
  }

  async function run() {
    if (!file) {
      setError("Please choose a resume file first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await analyzeResume({ file, role, jobDescription: showJd ? jd : "" });
      setReport(res);
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Analyze</div>
        <h1>Score a resume in seconds</h1>
        <p>
          Upload a resume, choose a target role or paste a job description, and RADAR grades it
          across six weighted dimensions with concrete fixes.
        </p>
      </div>

      {error && <div className="banner error">{error}</div>}

      <div className="card pad-lg" style={{ marginBottom: 22 }}>
        <div className="grid cols-2">
          <div>
            <span className="field-label">Resume file</span>
            <div
              className={`dropzone ${dragging ? "drag" : ""}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                pick(e.dataTransfer.files?.[0]);
              }}
            >
              {file ? (
                <div className="file-name">{file.name}</div>
              ) : (
                <div>
                  <div style={{ fontWeight: 600 }}>Drop your resume here</div>
                  <div className="hint">or click to browse · PDF, DOCX or TXT</div>
                </div>
              )}
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                style={{ display: "none" }}
                onChange={(e) => pick(e.target.files?.[0])}
              />
            </div>
          </div>

          <div>
            <label className="field">
              <span className="field-label">Target role</span>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="">— Select a role (optional) —</option>
                {roles.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>

            <button className="link-btn" onClick={() => setShowJd((s) => !s)}>
              {showJd ? "− Hide job description" : "+ Paste a job description instead"}
            </button>
            {showJd && (
              <textarea
                style={{ marginTop: 10 }}
                placeholder="Paste the full job description here for a tailored keyword & fit analysis…"
                value={jd}
                onChange={(e) => setJd(e.target.value)}
              />
            )}
          </div>
        </div>

        <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center" }}>
          <button className="btn primary" onClick={run} disabled={loading}>
            {loading ? <span className="spinner" /> : null}
            {loading ? "Analyzing…" : "Analyze resume"}
          </button>
          {file && (
            <button
              className="btn ghost"
              onClick={() => {
                setFile(null);
                setReport(null);
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {report && <Results report={report} />}
    </div>
  );
}
