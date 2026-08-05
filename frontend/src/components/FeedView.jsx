import React, { useEffect, useState } from "react";
import { checkBoard, createApplication, getFeed, getPreferences, savePreferences } from "../api.js";

const SOURCE_HELP = {
  greenhouse: "From the careers URL boards.greenhouse.io/COMPANY — use the COMPANY part.",
  lever: "From the careers URL jobs.lever.co/COMPANY — use the COMPANY part.",
};

/**
 * The job feed.
 *
 * Postings come from companies' own applicant-tracking systems, which publish
 * their listings as open JSON. That is a supported route, unlike scraping the
 * big job boards, which block it and forbid it in their terms.
 *
 * Refreshed when you open the page rather than streamed — a handful of boards
 * is quick, and it is honest to call this a daily check rather than live.
 */
export default function FeedView({ onTracked }) {
  const [prefs, setPrefs] = useState(null);
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const p = await getPreferences();
      setPrefs(p.preferences);
      if ((p.preferences.companies || []).length === 0) {
        setEditing(true);
        setFeed({ jobs: [], problems: [], configured: false });
      } else {
        setFeed(await getFeed());
      }
    } catch (e) {
      setError(e.message || "Couldn't load your feed.");
    } finally {
      setLoading(false);
    }
  }

  async function persist(next) {
    setPrefs(next);
    await savePreferences(next);
  }

  async function track(job) {
    setAdding(job.url);
    setError("");
    try {
      await createApplication({
        url: job.url,
        company: job.company,
        title: job.title,
        location: job.location,
        job_type: job.internship ? "Internship" : "Full-time",
        work_mode: job.remote ? "Remote" : "",
        generate_resume: false,
      });
      setFeed((f) => ({
        ...f,
        jobs: f.jobs.map((j) => (j.url === job.url ? { ...j, tracked: true } : j)),
      }));
      onTracked?.();
    } catch (e) {
      setError(e.message || "Couldn't add that to your tracker.");
    } finally {
      setAdding(null);
    }
  }

  if (loading) return <div className="empty">Checking the boards…</div>;

  const jobs = feed?.jobs || [];

  return (
    <div className="fade-in">
      <div className="page-head">
        <div className="eyebrow">Feed</div>
        <h1>Open roles today</h1>
        <p>
          Read straight from each company's own job board. Add the companies you care about, say
          what you're looking for, and this checks them for you.
        </p>
      </div>

      {error && <div className="banner error">{error}</div>}

      {prefs && (
        <PreferencesPanel
          prefs={prefs}
          open={editing}
          onToggle={() => setEditing((v) => !v)}
          onSave={async (next) => {
            await persist(next);
            setEditing(false);
            load();
          }}
        />
      )}

      {feed?.problems?.length > 0 && (
        <div className="banner info" style={{ marginTop: 18 }}>
          {feed.problems.map((p) => `${p.token}: ${p.error}`).join(" · ")}
        </div>
      )}

      {feed?.configured && (
        <div
          style={{
            marginTop: 22,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div className="section-title" style={{ margin: 0 }}>
            {jobs.length} matching {jobs.length === 1 ? "role" : "roles"}
          </div>
          <button className="link-btn" onClick={load}>
            Check again
          </button>
        </div>
      )}

      {feed?.configured && jobs.length === 0 && (
        <div className="empty">
          Nothing matched today. Loosen your filters, or add more companies.
        </div>
      )}

      <div style={{ marginTop: 16, display: "grid", gap: 12 }}>
        {jobs.map((job) => (
          <div className="card" key={`${job.source}-${job.external_id}`}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 14,
                alignItems: "flex-start",
                flexWrap: "wrap",
              }}
            >
              <div style={{ minWidth: 0, flex: "1 1 280px" }}>
                <div style={{ fontSize: 15.5, fontWeight: 600 }}>{job.title}</div>
                <div className="muted" style={{ marginTop: 2 }}>
                  {job.company}
                  {job.location ? ` · ${job.location}` : ""}
                  {job.posted_at ? ` · posted ${job.posted_at}` : ""}
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {job.internship && <span className="chip">Internship</span>}
                {job.remote && <span className="chip">Remote</span>}
              </div>
            </div>

            <div style={{ marginTop: 14, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <a
                className="btn ghost"
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ padding: "9px 16px", textDecoration: "none" }}
              >
                View posting
              </a>
              <button
                className="btn primary"
                onClick={() => track(job)}
                disabled={job.tracked || adding === job.url}
              >
                {adding === job.url && <span className="spinner" />}
                {job.tracked ? "In your tracker" : "Track this"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Which companies to watch, and what counts as a match. */
function PreferencesPanel({ prefs, open, onToggle, onSave }) {
  const [draft, setDraft] = useState(prefs);
  const [source, setSource] = useState("greenhouse");
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  function set(key, value) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  const asList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

  async function addBoard() {
    setChecking(true);
    setNote("");
    try {
      // Confirm the board exists before saving it, so a typo is caught here
      // rather than showing up as a permanently empty feed.
      const res = await checkBoard({ source, token });
      set("companies", [
        ...(draft.companies || []),
        { source, token: token.trim(), label: res.company || "" },
      ]);
      setNote(`Found ${res.count} open ${res.count === 1 ? "role" : "roles"} at ${res.company}.`);
      setToken("");
    } catch (e) {
      setNote(e.message || "Couldn't read that board.");
    } finally {
      setChecking(false);
    }
  }

  if (!open) {
    return (
      <div className="card" style={{ marginTop: 4 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div className="muted">
            Watching {(prefs.companies || []).length}{" "}
            {(prefs.companies || []).length === 1 ? "company" : "companies"}
            {prefs.roles?.length ? ` · ${prefs.roles.join(", ")}` : ""}
            {prefs.internships_only ? " · internships only" : ""}
            {prefs.remote_only ? " · remote only" : ""}
          </div>
          <button className="link-btn" onClick={onToggle}>
            Edit
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="card pad-lg">
      <div className="section-title">What should this watch?</div>

      <div className="muted" style={{ marginBottom: 16 }}>
        Add companies by their job-board name. {SOURCE_HELP[source]}
      </div>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label className="field" style={{ marginBottom: 0, flex: "0 0 150px" }}>
          <span className="field-label">Board</span>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
          </select>
        </label>
        <label className="field" style={{ marginBottom: 0, flex: "1 1 220px" }}>
          <span className="field-label">Company name</span>
          <input
            type="text"
            placeholder="stripe"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        <button className="btn ghost" onClick={addBoard} disabled={!token.trim() || checking}>
          {checking && <span className="spinner" />}
          {checking ? "Checking…" : "Add"}
        </button>
      </div>

      {note && (
        <div className="banner info" style={{ marginTop: 14, marginBottom: 0 }}>
          {note}
        </div>
      )}

      {(draft.companies || []).length > 0 && (
        <div className="chips" style={{ marginTop: 16 }}>
          {draft.companies.map((c, i) => (
            <span className="chip" key={`${c.source}-${c.token}-${i}`}>
              {c.label || c.token}
              <button
                className="link-btn"
                style={{ marginLeft: 8, color: "var(--critical)" }}
                onClick={() =>
                  set("companies", draft.companies.filter((_, j) => j !== i))
                }
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="grid cols-2" style={{ marginTop: 22 }}>
        <label className="field" style={{ marginBottom: 0 }}>
          <span className="field-label">Roles you want (comma separated)</span>
          <input
            type="text"
            placeholder="backend, machine learning, sde"
            value={(draft.roles || []).join(", ")}
            onChange={(e) => set("roles", asList(e.target.value))}
          />
        </label>
        <label className="field" style={{ marginBottom: 0 }}>
          <span className="field-label">Locations (comma separated)</span>
          <input
            type="text"
            placeholder="Bengaluru, Hyderabad"
            value={(draft.locations || []).join(", ")}
            onChange={(e) => set("locations", asList(e.target.value))}
          />
        </label>
      </div>

      <div style={{ marginTop: 18, display: "flex", gap: 20, flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={!!draft.internships_only}
            onChange={(e) => set("internships_only", e.target.checked)}
            style={{ width: "auto" }}
          />
          <span>Internships only</span>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={!!draft.remote_only}
            onChange={(e) => set("remote_only", e.target.checked)}
            style={{ width: "auto" }}
          />
          <span>Remote only</span>
        </label>
      </div>

      <div style={{ marginTop: 22, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button
          className="btn primary"
          onClick={async () => {
            setSaving(true);
            await onSave(draft);
            setSaving(false);
          }}
          disabled={saving}
        >
          {saving && <span className="spinner" />}
          Save and check
        </button>
        {(prefs.companies || []).length > 0 && (
          <button className="btn ghost" onClick={onToggle} disabled={saving}>
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
