import React, { useState } from "react";
import { login, signup, setToken } from "../api.js";

/**
 * Sign in / create account.
 *
 * The two modes share one form; only the submit target and the optional name
 * field differ. On success the JWT is stored and the parent is handed the user.
 */
export default function AuthView({ onSignedIn, notice }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isSignup = mode === "signup";

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
    setError("");
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = isSignup ? await signup(form) : await login(form);
      setToken(res.token);
      onSignedIn(res.user);
    } catch (err) {
      setError(err.message || "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ width: "100%", maxWidth: 420 }}>
        <div className="page-head" style={{ textAlign: "center", marginBottom: 22 }}>
          <div className="eyebrow">RADAR</div>
          <h1 style={{ fontSize: 32 }}>{isSignup ? "Create your account" : "Welcome back"}</h1>
          <p style={{ margin: "10px auto 0" }}>
            {isSignup
              ? "Your profile, resumes and tracked applications stay private to your account."
              : "Sign in to pick up your applications where you left them."}
          </p>
        </div>

        <form className="card pad-lg" onSubmit={submit}>
          {notice && <div className="banner info">{notice}</div>}
          {error && <div className="banner error">{error}</div>}

          {isSignup && (
            <label className="field">
              <span className="field-label">Name</span>
              <input
                type="text"
                autoComplete="name"
                placeholder="Your name"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </label>
          )}

          <label className="field">
            <span className="field-label">Email</span>
            <input
              type="text"
              autoComplete="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
            />
          </label>

          <label className="field" style={{ marginBottom: 8 }}>
            <span className="field-label">Password</span>
            <input
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              placeholder={isSignup ? "At least 8 characters" : "Your password"}
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
            />
          </label>

          <button
            className="btn primary"
            type="submit"
            style={{ width: "100%", marginTop: 12 }}
            disabled={busy || !form.email.trim() || !form.password}
          >
            {busy && <span className="spinner" />}
            {busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
          </button>

          <div style={{ marginTop: 16, textAlign: "center" }}>
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                setMode(isSignup ? "login" : "signup");
                setError("");
              }}
            >
              {isSignup
                ? "Already have an account? Sign in"
                : "New here? Create an account"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
