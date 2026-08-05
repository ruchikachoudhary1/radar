import React, { useEffect, useState } from "react";
import { deleteAccount, getProfile, saveProfile, setToken } from "../api.js";

const CONTACT = [
  ["name", "Full name", "Aditya Sharma"],
  ["email", "Email", "aditya.sharma@gmail.com"],
  ["phone", "Phone", "+91 98765 43210"],
  ["location", "Location", "Bengaluru, India"],
  ["linkedin", "LinkedIn", "linkedin.com/in/aditya-sharma"],
  ["github", "GitHub / portfolio", "github.com/adityasharma"],
];

const BLOCKS = [
  ["summary", "Professional summary", "Final-year CS student targeting backend roles."],
  ["experience", "Experience", "Role — Company (dates)\nWhat you built and the result."],
  ["projects", "Projects", "Project name — stack\nWhat it does and its outcome."],
  ["education", "Education", "B.Tech Computer Science, XYZ University (2021–2025)\nCGPA 8.4"],
  ["certifications", "Certifications & awards", "Leave blank if none."],
];

/**
 * The master profile.
 *
 * Every tailored resume in the tracker is assembled from this, so it is filled
 * once — normally auto-populated from an analysed resume — and edited by hand
 * whenever a detail changes.
 */
export default function ProfileView({ onAccountDeleted }) {
  const [profile, setProfile] = useState(null);
  const [skillText, setSkillText] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getProfile()
      .then((res) => {
        setProfile(res.profile);
        setSkillText((res.profile.skills || []).join(", "));
      })
      .catch((e) => setError(e.message || "Couldn't load your profile."));
  }, []);

  function set(key, value) {
    setProfile((p) => ({ ...p, [key]: value }));
    setStatus("");
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...profile,
        skills: skillText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const res = await saveProfile(payload);
      setProfile(res.profile);
      setSkillText((res.profile.skills || []).join(", "));
      setStatus(
        res.usable
          ? "Saved. The tracker can now build resumes from this."
          : "Saved, but add your name plus some skills or experience before tailoring resumes."
      );
    } catch (e) {
      setError(e.message || "Couldn't save your profile.");
    } finally {
      setSaving(false);
    }
  }

  if (!profile) {
    return (
      <div>
        <div className="page-head">
          <div className="eyebrow">Profile</div>
          <h1>Your master profile</h1>
        </div>
        {error ? <div className="banner error">{error}</div> : <div className="empty">Loading…</div>}
      </div>
    );
  }

  return (
    <div className="fade-in">
      <div className="page-head">
        <div className="eyebrow">Profile</div>
        <h1>Your master profile</h1>
        <p>
          Fill this in once. Every resume the tracker builds for a job posting starts from these
          facts, so you never retype them. Analyse a resume on the Analyze tab to fill it
          automatically, then correct anything the parser got wrong.
        </p>
      </div>

      {error && <div className="banner error">{error}</div>}
      {status && <div className="banner info">{status}</div>}

      <div className="card pad-lg">
        <div className="section-title">Contact details</div>
        <div className="grid cols-2" style={{ marginTop: 16 }}>
          {CONTACT.map(([key, label, hint]) => (
            <label className="field" key={key} style={{ marginBottom: 0 }}>
              <span className="field-label">{label}</span>
              <input
                type="text"
                placeholder={hint}
                value={profile[key] || ""}
                onChange={(e) => set(key, e.target.value)}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="card pad-lg" style={{ marginTop: 20 }}>
        <div className="section-title">Skills</div>
        <div className="muted" style={{ marginBottom: 10 }}>
          Comma separated. The tailoring engine reorders these per job, leading with whatever the
          posting asks for.
        </div>
        <textarea
          placeholder="Python, FastAPI, React, PostgreSQL, Docker, Git"
          value={skillText}
          onChange={(e) => {
            setSkillText(e.target.value);
            setStatus("");
          }}
        />
      </div>

      <div className="card pad-lg" style={{ marginTop: 20 }}>
        <div className="section-title">Your experience</div>
        <div className="muted" style={{ marginBottom: 4 }}>
          Write these as you'd want them read. Nothing here is invented — the tailoring engine only
          re-emphasises what you put in.
        </div>
        {BLOCKS.map(([key, label, hint]) => (
          <label className="field" key={key} style={{ marginTop: 18, marginBottom: 0 }}>
            <span className="field-label">{label}</span>
            <textarea
              placeholder={hint}
              value={profile[key] || ""}
              onChange={(e) => set(key, e.target.value)}
            />
          </label>
        ))}
      </div>

      <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center" }}>
        <button className="btn primary" onClick={save} disabled={saving}>
          {saving && <span className="spinner" />}
          {saving ? "Saving…" : "Save profile"}
        </button>
      </div>

      <DangerZone onDeleted={onAccountDeleted} />
    </div>
  );
}

/**
 * Account deletion.
 *
 * Deliberately awkward: it takes a second click and typing the word, because
 * this removes every resume, score and tracked application the account has,
 * and there is no undo.
 */
function DangerZone({ onDeleted }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await deleteAccount();
      setToken("");
      onDeleted?.();
    } catch (e) {
      setError(e.message || "Couldn't delete the account.");
      setBusy(false);
    }
  }

  return (
    <div className="card pad-lg" style={{ marginTop: 28, borderColor: "rgba(224,86,86,0.3)" }}>
      <div className="section-title" style={{ color: "var(--critical)" }}>
        Delete account
      </div>
      <div className="muted">
        Removes your profile, every scored resume and every tracked application. This cannot be
        undone.
      </div>

      {error && (
        <div className="banner error" style={{ marginTop: 14, marginBottom: 0 }}>
          {error}
        </div>
      )}

      {!open ? (
        <button
          className="btn ghost"
          style={{ marginTop: 16, color: "var(--critical)" }}
          onClick={() => setOpen(true)}
        >
          Delete my account
        </button>
      ) : (
        <div style={{ marginTop: 16 }}>
          <label className="field" style={{ maxWidth: 320, marginBottom: 12 }}>
            <span className="field-label">Type DELETE to confirm</span>
            <input
              type="text"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="DELETE"
            />
          </label>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button
              className="btn primary"
              style={{ background: "var(--critical)", color: "#fff" }}
              disabled={typed !== "DELETE" || busy}
              onClick={remove}
            >
              {busy && <span className="spinner" />}
              {busy ? "Deleting…" : "Permanently delete"}
            </button>
            <button
              className="btn ghost"
              onClick={() => {
                setOpen(false);
                setTyped("");
                setError("");
              }}
              disabled={busy}
            >
              Keep my account
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
