import React, { useState } from "react";
import { rewriteBullet } from "../api.js";

const EXAMPLES = [
  "Worked on the payment module and fixed bugs",
  "Responsible for maintaining the company website",
  "Helped the team with testing and deployment",
];

export default function RewriteView({ gemini }) {
  const [bullet, setBullet] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(-1);

  async function run() {
    if (!bullet.trim()) {
      setError("Enter a bullet point to rewrite.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await rewriteBullet(bullet, 3);
      setResult(res);
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function copy(text, i) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
      setTimeout(() => setCopied(-1), 1400);
    } catch (_) {
      /* clipboard may be blocked; ignore */
    }
  }

  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Rewrite</div>
        <h1>Turn weak bullets into strong ones</h1>
        <p>
          Paste a résumé bullet and RADAR rewrites it to lead with a strong action verb and a
          measurable result. {gemini ? "Powered by Gemini." : "Running the offline rule-based engine — add a Gemini key for richer rewrites."}
        </p>
      </div>

      {error && <div className="banner error">{error}</div>}

      <div className="card pad-lg" style={{ marginBottom: 22 }}>
        <span className="field-label">Your bullet point</span>
        <textarea
          value={bullet}
          onChange={(e) => setBullet(e.target.value)}
          placeholder="e.g. Worked on migrating the database and helped improve performance"
        />
        <div className="chips" style={{ marginTop: 12 }}>
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip" style={{ cursor: "pointer" }} onClick={() => setBullet(ex)}>
              {ex}
            </button>
          ))}
        </div>
        <div style={{ marginTop: 18 }}>
          <button className="btn primary" onClick={run} disabled={loading}>
            {loading ? <span className="spinner" /> : null}
            {loading ? "Rewriting…" : "Rewrite bullet"}
          </button>
        </div>
      </div>

      {result && (
        <div className="card pad-lg fade-in">
          <div className="section-title">
            Suggested rewrites <span className="pill" style={{ marginLeft: 8 }}>{result.engine}</span>
          </div>
          <p className="muted" style={{ marginBottom: 14 }}>
            Placeholders like [metric] mark where to insert your real numbers.
          </p>
          {result.variants.map((v, i) => (
            <div className="variant" key={i}>
              <div className="txt">{v}</div>
              <button className="btn ghost copy-btn" onClick={() => copy(v, i)}>
                {copied === i ? "Copied" : "Copy"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
