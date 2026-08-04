import React, { useEffect, useState } from "react";
import AnalyzeView from "./components/AnalyzeView.jsx";
import RewriteView from "./components/RewriteView.jsx";
import HistoryView from "./components/HistoryView.jsx";
import MethodView from "./components/MethodView.jsx";
import ProfileView from "./components/ProfileView.jsx";
import TrackerView from "./components/TrackerView.jsx";
import { getHealth } from "./api.js";

const NAV = [
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
  const [view, setView] = useState("analyze");
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setOffline(true));
  }, []);

  const roles = health?.roles || [
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "Data Scientist",
    "Machine Learning Engineer",
    "DevOps Engineer",
  ];

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
          <div style={{ marginTop: 14, opacity: 0.7 }}>
            Resume Analysis &amp; Role Alignment
          </div>
        </div>
      </aside>

      <main className="main">
        {offline && (
          <div className="banner error">
            Can't reach the backend API. Start it with <code>uvicorn main:app</code> in the backend
            folder, then reload.
          </div>
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
