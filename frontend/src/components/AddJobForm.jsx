import React, { useState } from "react";

const FIELDS = [
  ["title", "Role", "Backend Developer Intern"],
  ["company", "Company", "Acme Labs"],
  ["location", "Location", "Bengaluru"],
  ["stipend", "Stipend / salary", "₹25,000 /month"],
  ["duration", "Duration", "6 months"],
];

const blank = {
  title: "",
  company: "",
  location: "",
  stipend: "",
  duration: "",
  job_type: "",
  work_mode: "",
  notes: "",
  deadline: "",
};

/**
 * Add a posting by link, falling back to pasted text.
 *
 * Reading the link is best-effort — the big job boards render their postings in
 * JavaScript or block server-side requests outright — so a failed fetch opens
 * the paste box rather than reporting an error.
 */
export default function AddJobForm({ onAdd, onParse, facets, canTailor }) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [details, setDetails] = useState(blank);
  const [jdText, setJdText] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function set(key, value) {
    setDetails((d) => ({ ...d, [key]: value }));
  }

  function reset() {
    setUrl("");
    setText("");
    setShowPaste(false);
    setDetails(blank);
    setJdText("");
    setReviewing(false);
    setError("");
    setNotice("");
  }

  async function read() {
    setBusy("parse");
    setError("");
    setNotice("");
    try {
      const res = await onParse({ url, text });
      setDetails({ ...blank, ...res.meta, notes: "" });
      setJdText(res.jd_text || "");
      setReviewing(true);
      setNotice(
        res.source === "link"
          ? "Read straight from the link. Check the details below before saving."
          : "Read from the pasted description. Check the details below before saving."
      );
    } catch (e) {
      // A blocked or JavaScript-rendered page is the expected path here.
      setShowPaste(true);
      setError(e.message || "Couldn't read that link. Paste the description instead.");
    } finally {
      setBusy("");
    }
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      await onAdd({
        ...details,
        url,
        jd_text: jdText,
        status: "Saved",
        generate_resume: canTailor,
      });
      reset();
      setNotice(
        canTailor
          ? "Added, with a resume tailored to it."
          : "Added. Fill in your profile to get a tailored resume."
      );
    } catch (e) {
      setError(e.message || "Couldn't save that application.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="card pad-lg">
      <div className="section-title">Add a job</div>
      <div className="muted" style={{ marginBottom: 14 }}>
        Paste the link to the posting. RADAR reads it, fills in the details, and writes a resume
        aimed at it.
      </div>

      {error && <div className="banner error">{error}</div>}
      {notice && !error && <div className="banner info">{notice}</div>}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <input
          type="text"
          placeholder="https://company.com/careers/backend-intern"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={{ flex: "1 1 320px" }}
        />
        <button
          className="btn primary"
          onClick={read}
          disabled={!!busy || (!url.trim() && !text.trim())}
        >
          {busy === "parse" && <span className="spinner" />}
          {busy === "parse" ? "Reading…" : "Read posting"}
        </button>
      </div>

      <div style={{ marginTop: 10 }}>
        <button className="link-btn" onClick={() => setShowPaste((s) => !s)}>
          {showPaste ? "Hide the paste box" : "Or paste the job description instead"}
        </button>
      </div>

      {showPaste && (
        <label className="field" style={{ marginTop: 12, marginBottom: 0 }}>
          <span className="field-label">Job description</span>
          <textarea
            placeholder="Paste the full job description here — responsibilities, requirements, stipend, location."
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ minHeight: 150 }}
          />
        </label>
      )}

      {reviewing && (
        <div style={{ marginTop: 22, borderTop: "1px solid var(--border-soft)", paddingTop: 20 }}>
          <div className="section-title" style={{ fontSize: 16 }}>
            Check the details
          </div>
          <div className="muted" style={{ marginBottom: 14 }}>
            Anything RADAR couldn't find is blank — fill it in and it will be saved as you typed it.
          </div>

          <div className="grid cols-2">
            {FIELDS.map(([key, label, hint]) => (
              <label className="field" key={key} style={{ marginBottom: 0 }}>
                <span className="field-label">{label}</span>
                <input
                  type="text"
                  placeholder={hint}
                  value={details[key] || ""}
                  onChange={(e) => set(key, e.target.value)}
                />
              </label>
            ))}

            <label className="field" style={{ marginBottom: 0 }}>
              <span className="field-label">Type</span>
              <select value={details.job_type || ""} onChange={(e) => set("job_type", e.target.value)}>
                <option value="">Not specified</option>
                {(facets.job_types || []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>

            <label className="field" style={{ marginBottom: 0 }}>
              <span className="field-label">Work mode</span>
              <select
                value={details.work_mode || ""}
                onChange={(e) => set("work_mode", e.target.value)}
              >
                <option value="">Not specified</option>
                {(facets.work_modes || []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>

            <label className="field" style={{ marginBottom: 0 }}>
              <span className="field-label">Apply by</span>
              <input
                type="date"
                value={details.deadline || ""}
                onChange={(e) => set("deadline", e.target.value)}
              />
            </label>
          </div>

          <label className="field" style={{ marginTop: 18, marginBottom: 0 }}>
            <span className="field-label">Notes</span>
            <textarea
              placeholder="Referral contact, who to follow up with, anything you want to remember."
              value={details.notes || ""}
              onChange={(e) => set("notes", e.target.value)}
              style={{ minHeight: 80 }}
            />
          </label>

          <div style={{ marginTop: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="btn primary" onClick={save} disabled={!!busy}>
              {busy === "save" && <span className="spinner" />}
              {busy === "save"
                ? "Building your resume…"
                : canTailor
                ? "Save & build resume"
                : "Save application"}
            </button>
            <button className="btn ghost" onClick={reset} disabled={!!busy}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
