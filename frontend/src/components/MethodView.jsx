import React from "react";

const DIMENSIONS = [
  ["20", "Structure & Sections", "Detects the presence of contact, education, experience, skills and projects sections — the backbone an ATS parser expects."],
  ["25", "Role & Keyword Match", "Compares the resume against a curated skill bank for the target role, or against keywords extracted from a pasted job description."],
  ["20", "Impact & Quantification", "Measures how many achievement bullets carry a concrete number — %, time saved, users, scale — the signal recruiters scan for."],
  ["15", "Action Language", "Rewards strong action verbs (Built, Led, Optimized) and penalises weak openers ('worked on', 'responsible for')."],
  ["10", "Readability & Brevity", "Checks total length and average bullet length against early-career norms (one page, tight bullets)."],
  ["10", "Contact & Links", "Confirms email, phone, LinkedIn and GitHub are present and discoverable."],
];

const STACK = [
  ["Frontend", "React 18, Vite, hand-built SVG data-viz, custom design system"],
  ["Backend", "FastAPI, Pydantic, Uvicorn — typed REST API with auto OpenAPI docs"],
  ["NLP / ML", "scikit-learn TF-IDF + cosine similarity for JD matching"],
  ["AI", "Google Gemini for bullet rewriting, with a deterministic offline fallback"],
  ["Data", "SQLite persistence of every analysis"],
  ["Parsing", "pdfplumber and python-docx for PDF / Word extraction"],
];

export default function MethodView() {
  return (
    <div>
      <div className="page-head">
        <div className="eyebrow">Method</div>
        <h1>How the score is built</h1>
        <p>
          RADAR is deliberately transparent: every point is traceable to a rule, so the score is
          explainable rather than a black box. Here is the full rubric and the stack behind it.
        </p>
      </div>

      <div className="grid cols-2-1">
        <div className="card pad-lg">
          <div className="section-title">The 100-point rubric</div>
          <p className="muted" style={{ marginBottom: 6 }}>Six independent dimensions, weighted by hiring impact.</p>
          {DIMENSIONS.map(([w, name, desc]) => (
            <div className="method-item" key={name}>
              <h4>
                <span className="w">{w} pts</span> · {name}
              </h4>
              <p>{desc}</p>
            </div>
          ))}
        </div>

        <div className="card pad-lg">
          <div className="section-title">Tech stack</div>
          <p className="muted" style={{ marginBottom: 6 }}>Chosen to mirror a real product service.</p>
          {STACK.map(([k, v]) => (
            <div className="method-item" key={k}>
              <h4>{k}</h4>
              <p>{v}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
