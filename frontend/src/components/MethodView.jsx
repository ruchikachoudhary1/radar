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
  ["Data", "SQLAlchemy over PostgreSQL in production, SQLite locally — one switch, same code"],
  ["Accounts", "bcrypt password hashing, stateless JWT sessions, per-user data isolation"],
  ["Parsing", "pdfplumber and python-docx read uploads in; python-docx writes the .docx back out"],
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
  [
    "Cover letters",
    "Written from the same profile and posting as the resume, so the two cannot contradict each other. Where a number would strengthen a claim and the profile has none, both engines leave a marked [add detail] placeholder and the count is shown to the user. An unfinished letter you know about beats a finished-looking one with an invented metric in it.",
  ],
  [
    "Follow-up urgency",
    "Each application is graded from its stage, the date it was sent and the company's closing date: calm for the first week, a warning after seven days of silence, urgent after fourteen or once a deadline passes. The rule lives in one tested module rather than in the component, so the dashboard and the pipeline can never disagree about what needs chasing.",
  ],
];

const SECURITY = [
  [
    "Passwords",
    "Hashed with bcrypt, which is deliberately slow and salts every digest, so identical passwords produce different rows and a stolen table cannot be reversed with a lookup. The plain password is never stored, logged or returned.",
  ],
  [
    "Sessions",
    "Signed JWTs rather than server-side state, so the API survives the restarts a free hosting tier hands out. The trade-off is real: a token cannot be revoked before it expires, which is why the expiry is fourteen days rather than months.",
  ],
  [
    "Account isolation",
    "Every query filters on the owner inside the data layer, not in the route handlers, so a forgotten check in one endpoint cannot leak another account's resumes. Tests create two accounts and assert the second cannot read, modify or delete the first's applications.",
  ],
  [
    "Login throttling",
    "bcrypt makes each guess slow, but slow is not limited. Eight failures locks an address for fifteen minutes; a correct password clears the record so an ordinary typo costs nothing later.",
  ],
  [
    "Enumeration",
    "An unknown email and a wrong password return the same message, so the login form cannot be used to discover which addresses are registered.",
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

      <div className="card pad-lg" style={{ marginTop: 20 }}>
        <div className="section-title">Accounts and storage</div>
        <p className="muted" style={{ marginBottom: 6 }}>
          Free hosting gives a container a filesystem that is wiped on every deploy, restart and
          cold start, so a SQLite file there loses every account. The models sit on SQLAlchemy and
          one environment variable decides where data lives — a file locally, PostgreSQL in
          production, the same code and the same tests against both.
        </p>
        {SECURITY.map(([name, desc]) => (
          <div className="method-item" key={name}>
            <h4>{name}</h4>
            <p>{desc}</p>
          </div>
        ))}
      </div>

      <div className="card pad-lg" style={{ marginTop: 20 }}>
        <div className="section-title">Known limits</div>
        <p className="muted">
          Stated here rather than discovered later. The free backend sleeps after fifteen minutes,
          so the first request of the day waits roughly fifty seconds. Sessions expire at fourteen
          days with no refresh token. Posting fields are extracted with regexes and are left blank
          rather than guessed when a layout is unusual. Signup has no email verification.
        </p>
      </div>
    </div>
  );
}
