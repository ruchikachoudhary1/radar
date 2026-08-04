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
  ["AI", "Google Gemini for rewriting and tailoring, with a deterministic offline fallback"],
  ["Data", "SQLite — analyses, the master profile, and the application pipeline"],
  ["Parsing", "pdfplumber and python-docx in; python-docx and fpdf2 back out"],
];

const PIPELINE = [
  [
    "Gap-fill interview",
    "The rule engine compares a scored resume against the rubric and turns each shortfall into a question — a bullet with no number, a missing section, an absent link. Answers are folded back in and the resume is re-scored, so the improvement is measured, not asserted.",
  ],
  [
    "Master profile",
    "Resume text is parsed once into structured fields — contact, skills, experience, projects, education. Section headings are matched against an alias table, so 'Technical Skills' and 'Tech Stack' both resolve to the same field. Every field stays editable, because a visible wrong guess is safer than a silent one.",
  ],
  [
    "Posting ingestion",
    "A posting URL is fetched server-side and stripped to text with regex, no parser dependency. Because the fetch target is user-supplied, hostnames resolving to private, loopback or link-local addresses are refused — otherwise the deployed backend could be used to reach its own network. Boards that block bots or render in JavaScript fall back to pasted text.",
  ],
  [
    "Field extraction",
    "Pay, location, duration, work mode and job type are pulled with labelled-value regexes that stop at the next field, so 'Location: Pune. Stipend: ...' does not swallow the rest of the line. Anything not found is left blank rather than guessed.",
  ],
  [
    "Tailoring",
    "The profile is re-ranked against the posting's TF-IDF keywords so relevant skills lead, then rendered as a resume and re-scored for keyword coverage. The rule layer never adds a skill the profile lacks; Gemini, when configured, rewrites the prose under the same constraint.",
  ],
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

      <div className="card pad-lg" style={{ marginTop: 20 }}>
        <div className="section-title">From upload to a tailored application</div>
        <p className="muted" style={{ marginBottom: 6 }}>
          Every AI-assisted step has a deterministic engine underneath it. The rules decide what
          is true; the model only decides how it reads. That is why the app still works with no API
          key — and why nothing it writes can be an invention.
        </p>
        {PIPELINE.map(([name, desc]) => (
          <div className="method-item" key={name}>
            <h4>{name}</h4>
            <p>{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
