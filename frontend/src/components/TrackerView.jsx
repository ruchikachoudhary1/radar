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
  writeCoverLetter,
} from "../api.js";
import AddJobForm from "./AddJobForm.jsx";
import ApplicationCard from "./ApplicationCard.jsx";
import Skeleton from "./Skeleton.jsx";
import PipelineBoard from "./PipelineBoard.jsx";
import { useToast } from "./Toast.jsx";

const ALL = "All";
const BOARD_MIN_WIDTH = 760;

/** True when the viewport is too narrow for a five-column board. */
function useNarrowScreen(breakpoint = BOARD_MIN_WIDTH) {
  const query = `(max-width: ${breakpoint}px)`;
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches
  );

  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = (e) => setNarrow(e.matches);
    mq.addEventListener("change", update);
    setNarrow(mq.matches);
    return () => mq.removeEventListener("change", update);
  }, [query]);

  return narrow;
}

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
  const [layout, setLayout] = useState("board");
  const narrow = useNarrowScreen();
  const toast = useToast();
  // A five-column board does not fit a phone, so the list takes over there.
  const showBoard = layout === "board" && !narrow;

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
      toast(`Moved to ${status}.`, "good");
    } catch (e) {
      toast(e.message || "Couldn't update that application.", "error");
    }
  }

  /** Stop the follow-up clock once a company has actually come back. */
  async function markReplied(id) {
    setError("");
    try {
      const updated = await updateApplication(id, { replied: true });
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...updated } : it)));
      toast("Marked as replied — it will stop nagging you.", "good");
    } catch (e) {
      toast(e.message || "Couldn't update that application.", "error");
    }
  }

  async function remove(id) {
    setError("");
    try {
      await deleteApplication(id);
      setItems((prev) => prev.filter((it) => it.id !== id));
      if (open?.id === id) setOpen(null);
      toast("Removed from your tracker.", "info");
    } catch (e) {
      toast(e.message || "Couldn't delete that application.", "error");
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
      toast("Resume rebuilt from your profile.", "good");
      return res;
    } catch (e) {
      toast(e.message || "Couldn't rebuild that resume.", "error");
      return null;
    }
  }

  const needsFollowUp = (it) => ["warn", "urgent"].includes(it.urgency?.level);
  const followUpCount = items.filter(needsFollowUp).length;

  async function buildLetter(id) {
    setError("");
    try {
      const res = await writeCoverLetter(id);
      setOpen(res.application);
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...res.application } : it)));
      const left = res.placeholders;
      toast(
        left > 0
          ? `Cover letter written — ${left} ${left === 1 ? "spot needs" : "spots need"} filling in.`
          : "Cover letter written.",
        left > 0 ? "info" : "good"
      );
      return res;
    } catch (e) {
      toast(e.message || "Couldn't write that cover letter.", "error");
      return null;
    }
  }

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

          {!narrow && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="muted" style={{ minWidth: 74 }}>View</span>
              <div className="chips" style={{ marginTop: 0 }}>
                <button
                  className={`chip ${layout === "board" ? "on" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => setLayout("board")}
                >
                  Board
                </button>
                <button
                  className={`chip ${layout === "list" ? "on" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => setLayout("list")}
                >
                  List
                </button>
              </div>
            </div>
          )}

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
        <Skeleton rows={3} label="Loading your applications" />
      ) : shown.length === 0 ? (
        <div className="empty">
          {items.length === 0
            ? "No applications yet. Paste a job link above to add your first."
            : onlyFollowUp
            ? "Nothing needs chasing right now."
            : "No applications match these filters."}
        </div>
      ) : showBoard ? (
        <PipelineBoard
          items={shown}
          statuses={facets.statuses}
          onMove={move}
          onView={view}
          onReplied={markReplied}
        />
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
          onWriteLetter={buildLetter}
        />
      )}
    </div>
  );
}

/** The tailored resume and cover letter for one application, with exports. */
function ResumeDrawer({ app, onClose, onRebuild, onDownload, onWriteLetter }) {
  const [busy, setBusy] = useState("");
  const [tab, setTab] = useState("resume");

  const stem = `${app.company || "resume"}-${app.title || "role"}`
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();

  async function save(format) {
    setBusy(format);
    try {
      await onDownload(app.resume_text, format, stem);
    } finally {
      setBusy("");
    }
  }

  async function saveLetter(format) {
    setBusy(`letter-${format}`);
    try {
      await onDownload(app.cover_letter, format, `${stem}-cover-letter`);
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

      <div className="chips" style={{ marginTop: 14 }}>
        <button
          className={`chip ${tab === "resume" ? "on" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setTab("resume")}
        >
          Resume
        </button>
        <button
          className={`chip ${tab === "letter" ? "on" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={() => setTab("letter")}
        >
          Cover letter
        </button>
      </div>

      {tab === "letter" ? (
        <CoverLetterPanel
          app={app}
          busy={busy}
          setBusy={setBusy}
          onWriteLetter={onWriteLetter}
          onSave={saveLetter}
        />
      ) : app.resume_text ? (
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

/**
 * The cover letter for one application.
 *
 * Both engines are told to leave a marked [add …] placeholder rather than
 * invent a specific, so the count of those is surfaced rather than hidden —
 * an unfinished letter the user knows about beats a complete-looking one with
 * a fabricated detail in it.
 */
function CoverLetterPanel({ app, busy, setBusy, onWriteLetter, onSave }) {
  const [placeholders, setPlaceholders] = useState(null);

  async function write() {
    setBusy("letter");
    const res = await onWriteLetter(app.id);
    if (res) setPlaceholders(res.placeholders);
    setBusy("");
  }

  if (!app.cover_letter) {
    return (
      <div style={{ marginTop: 18 }}>
        <div className="muted" style={{ marginBottom: 14 }}>
          Written from your master profile and this posting — the same source as the resume, so
          the two agree with each other.
        </div>
        <button className="btn primary" onClick={write} disabled={!!busy}>
          {busy === "letter" && <span className="spinner" />}
          Write a cover letter
        </button>
      </div>
    );
  }

  return (
    <>
      {placeholders > 0 && (
        <div className="banner info" style={{ marginTop: 16, marginBottom: 0 }}>
          {placeholders === 1
            ? "One spot is marked [add …] — fill it in before you send this."
            : `${placeholders} spots are marked [add …] — fill them in before you send this.`}{" "}
          Nothing was invented to cover the gap.
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
          lineHeight: 1.7,
          maxHeight: 460,
          overflowY: "auto",
        }}
      >
        {app.cover_letter}
      </pre>

      <div style={{ marginTop: 18, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button className="btn primary" onClick={() => onSave("docx")} disabled={!!busy}>
          {busy === "letter-docx" && <span className="spinner" />}
          Download .docx
        </button>
        <button
          className="btn ghost"
          onClick={() => navigator.clipboard?.writeText(app.cover_letter)}
        >
          Copy text
        </button>
        <button className="btn ghost" onClick={write} disabled={!!busy}>
          {busy === "letter" && <span className="spinner" />}
          Rewrite
        </button>
      </div>
    </>
  );
}
