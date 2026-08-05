import React, { useEffect, useState } from "react";
import AnalyzeView from "./components/AnalyzeView.jsx";
import RewriteView from "./components/RewriteView.jsx";
import HistoryView from "./components/HistoryView.jsx";
import MethodView from "./components/MethodView.jsx";
import ProfileView from "./components/ProfileView.jsx";
import TrackerView from "./components/TrackerView.jsx";
import AuthView from "./components/AuthView.jsx";
import DashboardView from "./components/DashboardView.jsx";
import { getHealth, getMe, getToken, setToken, onSessionExpired } from "./api.js";

const NAV = [
  { id: "dashboard", label: "Dashboard" },
  { id: "analyze", label: "Analyze" },
  { id: "tracker", label: "Applications" },
  { id: "profile", label: "Profile" },
  { id: "rewrite", label: "Rewrite" },
  { id: "history", label: "History" },
  { id: "method", label: "Method" },
];

function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
      <path d="M12 12 L19 6" strokeLinecap="round" />
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setOffline(true));
  }, []);

  // Resume an existing session on load. A stored token that the server no
  // longer accepts is cleared by the api layer, so this just falls through
  // to the sign-in screen.
  useEffect(() => {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    getMe()
      .then((res) => setUser(res.user))
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);

  // If any request comes back 401 mid-session, drop straight to sign-in.
  useEffect(
    () =>
      onSessionExpired((detail) => {
        setUser(null);
        setNotice(detail || "Your session expired. Please sign in again.");
      }),
    []
  );

  function signOut() {
    setToken("");
    setUser(null);
    setView("dashboard");
    setNotice("");
  }

  const roles = health?.roles || [
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "Data Scientist",
    "Machine Learning Engineer",
    "DevOps Engineer",
  ];

  if (checking) {
    return <div className="empty" style={{ paddingTop: "22vh" }}>Loading…</div>;
  }

  if (!user) {
    return (
      <AuthView
        notice={notice || (offline ? "Can't reach the backend API — start it and reload." : "")}
        onSignedIn={(u) => {
          setUser(u);
          setNotice("");
        }}
      />
    );
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <BrandMark />
          </div>
          <div>
            <div className="brand-name">RADAR</div>
            <div className="brand-sub">Resume Intelligence</div>
          </div>
        </div>

        <nav className="nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${view === n.id ? "active" : ""}`}
              onClick={() => setView(n.id)}
            >
              <span className="dot" />
              {n.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="status-pill">
            <span className={`live ${offline ? "off" : ""}`} />
            {offline ? "API offline" : "API online"}
          </div>
          {health && (
            <div style={{ marginTop: 8 }}>
              AI rewrite: {health.gemini_configured ? "Gemini" : "offline engine"}
            </div>
          )}
          <div style={{ marginTop: 14, wordBreak: "break-all" }}>
            {user.name || user.email}
          </div>
          <button className="link-btn" style={{ marginTop: 6 }} onClick={signOut}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        {offline && (
          <div className="banner error">
            Can't reach the backend API. Start it with <code>uvicorn main:app</code> in the backend
            folder, then reload.
          </div>
        )}
        {view === "dashboard" && (
          <DashboardView onNavigate={setView} userName={user.name} />
        )}
        {view === "analyze" && <AnalyzeView roles={roles} />}
        {view === "tracker" && <TrackerView />}
        {view === "profile" && <ProfileView />}
        {view === "rewrite" && <RewriteView gemini={health?.gemini_configured} />}
        {view === "history" && <HistoryView />}
        {view === "method" && <MethodView />}
      </main>
    </div>
  );
}
