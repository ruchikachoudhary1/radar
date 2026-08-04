import React, { useEffect, useState } from "react";
import {
  createApplication,
  deleteApplication,
  getApplication,
  getApplications,
  getProfile,
  parseJob,
  retailorApplication,
  updateApplication,
  downloadResume,
} from "../api.js";
import AddJobForm from "./AddJobForm.jsx";
import ApplicationCard from "./ApplicationCard.jsx";

const ALL = "All";

/**
 * The application tracker.
 *
 * Applications live in a status pipeline (Saved → Applied → Interviewing →
 * Offer / Rejected) and are filtered by the facts pulled off the posting:
 * type, work mode and location.
 */
export default function TrackerView() {
  const [items, setItems] = useState([]);
  const [facets, setFacets] = useState({ statuses: [], job_types: [], work_modes: [] });
  const [profileReady, setProfileReady] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);
  const [filters, setFilters] = useState({ status: ALL, job_type: ALL, work_mode: ALL });
  const [onlyFollowUp, setOnlyFollowUp] = useState(false);

  useEffect(() => {
    refresh();
    getProfile()
      .then((res) => setProfileReady(res.usable))
      .catch(() => setProfileReady(true));
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      const res = await getApplications();
      setItems(res.items || []);
      setFacets({
        statuses: res.statuses || [],
        job_types: res.job_types || [],
        work_modes: res.work_modes || [],
      });
    } catch (e) {
      setError(e.message || "Couldn't load your applications.");
    } finally {
      setLoading(false);
    }
  }

  async function addJob(payload) {
    const created = await createApplication(payload);
    setItems((prev) => [created, ...prev]);
    return created;
  }

  async function move(id, status) {
    setError("");
    try {
      const updated = await updateApplication(id, { status });
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...updated } : it)));
    } catch (e) {
      setError(e.message || "Couldn't update that application.");
    }
  }

  /** Stop the follow-up clock once a company has actually come back. */
  async function markReplied(id) {
    setError("");
    try {
      const updated = await updateApplication(id, { replied: true });
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...updated } : it)));
    } catch (e) {
      setError(e.message || "Couldn't update that application.");
    }
  }

  async function remove(id) {
    setError("");
    try {
      await deleteApplication(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
      if (open?.id === id) setOpen(null);
    } catch (e) {
      setError(e.message || "Couldn't delete that application.");
    }
  }

  async function view(id) {
    setError("");
    try {
      setOpen(await getApplication(id));
    } catch (e) {
      setError(e.message || "Couldn't open that application.");
    }
  }

  async function rebuild(id) {
    setError("");
    try {
      const res = await retailorApplication(id);
      setOpen(res.application);
      setItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, ...res.application } : it))
      );
      return res;
    } catch (e) {
      setError(e.message || "Couldn't rebuild that resume.");
      return null;
    }
  }

  const needsFollowUp = (it) => ["warn", "urgent"].includes(it.urgency?.level);
  const followUpCount = items.filter(needsFollowUp).length;

  const shown = items.filter(
    (it) =>
      (filters.status === ALL || it.status === filters.status) &&
      (filters.job_type === ALL || it.job_type === filters.job_type) &&
      (filters.work_mode === ALL || it.work_mode === filters.work_mode) &&
      (!onlyFollowUp || needsFollowUp(it))
  );

  const counts = {};
  for (const it of items) counts[it.status] = (counts[it.status] || 0) + 1;

  function filterRow(key, label, options) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="muted" style={{ minWidth: 74 }}>{label}</span>
        <div className="chips" style={{ marginTop: 0 }}>
          {[ALL, ...options].map((opt) => (
            <button
              key={opt}
              className={`chip ${filters[key] === opt ? "on" : ""}`}
              style={{ cursor: "pointer" }}
              onClick={() => setFilters((f) => ({ ...f, [key]: opt }))}
            >
              {opt}
              {key === "status" && opt !== ALL && counts[opt] ? ` (${counts[opt]})` : ""}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div className="eyebrow">Tracker</div>
        <h1>Applications</h1>
        <p>
          Paste a job link and RADAR reads the posting, files it by pay, location, work mode and
          duration, then writes a resume for it from your master profile. Move each one along the
          pipeline as you hear back.
        </p>
      </div>

      {!profileReady && (
        <div className="banner info">
          Your master profile is empty, so resumes can't be tailored yet. Fill in the Profile tab
          first — you can still save job postings in the meantime.
        </div>
      )}
      {error && <div className="banner error">{error}</div>}

      <AddJobForm onAdd={addJob} onParse={parseJob} facets={facets} canTailor={profileReady} />

      <div className="card" style={{ marginTop: 20 }}>
        <div style={{ display: "grid", gap: 12 }}>
          {filterRow("status", "Stage", facets.statuses)}
          {filterRow("job_type", "Type", facets.job_types)}
          {filterRow("work_mode", "Mode", facets.work_modes)}

          {followUpCount > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="muted" style={{ minWidth: 74 }}>Chase</span>
              <button
                className={`chip ${onlyFollowUp ? "off" : ""}`}
                style={{ cursor: "pointer" }}
                onClick={() => setOnlyFollowUp((v) => !v)}
              >
                {followUpCount} need{followUpCount === 1 ? "s" : ""} following up
              </button>
            </div>
          )}
        </div>
      </div>

      {loading ? (
        <div className="empty">Loading…</div>
      ) : shown.length === 0 ? (
        <div className="empty">
          {items.length === 0
            ? "No applications yet. Paste a job link above to add your first."
            : onlyFollowUp
            ? "Nothing needs chasing right now."
            : "No applications match these filters."}
        </div>
      ) : (
        <div style={{ marginTop: 20, display: "grid", gap: 14 }}>
          {shown.map((it) => (
            <ApplicationCard
              key={it.id}
              app={it}
              statuses={facets.statuses}
              onMove={move}
              onDelete={remove}
              onView={view}
              onReplied={markReplied}
            />
          ))}
        </div>
      )}

      {open && (
        <ResumeDrawer
          app={open}
          onClose={() => setOpen(null)}
          onRebuild={rebuild}
          onDownload={downloadResume}
        />
      )}
    </div>
  );
}

/** The tailored resume for one application, with export buttons. */
function ResumeDrawer({ app, onClose, onRebuild, onDownload }) {
  const [busy, setBusy] = useState("");

  async function save(format) {
    setBusy(format);
    try {
      const stem = `${app.company || "resume"}-${app.title || "role"}`
        .replace(/[^a-zA-Z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
        .toLowerCase();
      await onDownload(app.resume_text, format, stem);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="card pad-lg fade-in" style={{ marginTop: 22 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <div className="section-title">
            {app.title || "Untitled role"}
            {app.company ? ` · ${app.company}` : ""}
          </div>
          <div className="muted">
            {app.resume_text
              ? `Written by ${app.engine === "gemini" ? "Gemini" : "the offline engine"}`
              : "No resume built for this one yet"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {app.match_score != null && <span className="pill">{app.match_score}% keyword match</span>}
          <button className="link-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>

      {app.resume_text ? (
        <>
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
            {app.resume_text}
          </pre>
          <div style={{ marginTop: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button className="btn primary" onClick={() => save("docx")} disabled={!!busy}>
              {busy === "docx" && <span className="spinner" />}
              Download .docx
            </button>
            <button className="btn ghost" onClick={() => save("pdf")} disabled={!!busy}>
              {busy === "pdf" && <span className="spinner" />}
              Download .pdf
            </button>
            <button
              className="btn ghost"
              onClick={() => navigator.clipboard?.writeText(app.resume_text)}
            >
              Copy text
            </button>
            <button
              className="btn ghost"
              onClick={async () => {
                setBusy("rebuild");
                await onRebuild(app.id);
                setBusy("");
              }}
              disabled={!!busy}
            >
              {busy === "rebuild" && <span className="spinner" />}
              Rebuild from profile
            </button>
          </div>
        </>
      ) : (
        <div style={{ marginTop: 16 }}>
          <button
            className="btn primary"
            onClick={async () => {
              setBusy("rebuild");
              await onRebuild(app.id);
              setBusy("");
            }}
            disabled={!!busy}
          >
            {busy === "rebuild" && <span className="spinner" />}
            Build a resume for this job
          </button>
        </div>
      )}
    </div>
  );
}
