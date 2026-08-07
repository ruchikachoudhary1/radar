# RADAR — Resume Analysis & Role Alignment

[![tests](https://github.com/ruchikachoudhary1/radar/actions/workflows/tests.yml/badge.svg)](https://github.com/ruchikachoudhary1/radar/actions/workflows/tests.yml)

RADAR is a full-stack web application that scores a resume against a target role
or a pasted job description, explains **why** it scored that way across six
weighted dimensions, and rewrites weak bullet points into strong, quantified
ones. It is built as a real product service: a typed REST API, an NLP matching
layer, a persistence layer, an optional LLM integration with a graceful offline
fallback, a test suite, and containerised deployment.

> **Live demo:** https://radar-six-iota.vercel.app

---

## Why this project is interesting

Most "resume checker" projects stop at counting keywords. RADAR is built to show
engineering breadth end-to-end:

- **A transparent scoring model.** Six independent dimensions sum to 100. Every
  point is traceable to a rule, so the score is explainable rather than a black
  box — see the in-app **Method** page.
- **Real NLP.** Job-description fit uses TF-IDF vectorisation + cosine similarity
  (scikit-learn), not naive string matching, and reports keyword coverage.
- **An LLM feature done responsibly.** Bullet rewriting uses Google Gemini when a
  key is present and falls back to a deterministic rule-based rewriter when it is
  not — the app is fully functional offline.
- **Real accounts.** bcrypt password hashing, stateless JWT sessions, and
  per-user data isolation enforced in the data layer rather than in the route
  handlers — so a forgotten check in one endpoint cannot leak another account's
  resumes.
- **Storage that survives.** Free hosting gives a container an ephemeral
  filesystem, so a SQLite file there is wiped on every deploy and restart. The
  models sit on SQLAlchemy and one environment variable chooses the backend:
  SQLite locally, PostgreSQL in production, same code and same tests on both.
- **Production shape.** Typed FastAPI backend with auto-generated OpenAPI docs,
  origin-restricted CORS, login throttling, Dockerfiles for both services, an
  nginx reverse proxy, a Docker Compose stack, and one-click cloud deploy
  configs.
- **Tested.** 167 tests covering the scoring engine, parser, matcher, rewriter,
  follow-up rules, cover letters, the job feed, and account isolation.

## Features

### Analysis

- Upload a resume (PDF, DOCX or TXT) and get an overall score out of 100 with a
  letter grade and a plain-English verdict.
- Six-dimension breakdown: Structure, Role/Keyword match, Impact & Quantification,
  Action Language, Readability, and Contact & Links — each with its own status
  colour and specific suggestions.
- Target-role scoring against curated skill banks, **or** paste a full job
  description for tailored keyword coverage + TF-IDF similarity.
- Matched vs. missing keyword chips.
- AI bullet rewriter with copy-to-clipboard.
- Analysis history persisted to a database.

### Gap-fill interview

- After scoring, RADAR works out *which facts are missing* that would raise the
  score and asks about them — a bullet with no metric, an absent section, a
  missing link.
- Answers are folded back into a rewritten resume, which is then **re-scored
  against the original**, so the improvement is measured rather than claimed.
- The rule engine decides *which* gaps exist; Gemini only rewords the questions
  and writes the final prose. Every question traces back to a rubric dimension.

### Application tracker

- Paste a **job posting link** — RADAR fetches it, strips it to text, and pulls
  out the role, company, stipend/salary, location, work mode, duration and
  whether it's an internship or a full-time job. Boards that block bots or render
  in JavaScript fall back to pasting the description.
- A **master profile** — auto-filled from an analysed resume, then editable —
  supplies your details once so you never retype them.
- Each saved posting gets a **resume tailored to it**, built from the profile and
  re-ranked against the posting's keywords, with its keyword-match score shown.
- Applications move through a status pipeline (Saved → Applied → Interviewing →
  Offer / Rejected) and filter by type, work mode and stage.
- Each application carries a **deadline** and a **follow-up verdict**: calm for
  the first week, a warning after seven days of silence, urgent after fourteen or
  once the closing date passes. The rule lives in one tested module, so the
  dashboard and the pipeline cannot disagree about what needs chasing.
- A **cover letter** per application, written from the same profile and posting
  as the resume. Where a number would help and the profile has none, it leaves a
  marked `[add detail]` placeholder and tells you how many are left, rather than
  inventing one.
- Export any generated resume or letter to **.docx, .pdf or .txt**.

### Job feed

- Add the companies you care about by their job-board name. RADAR reads their
  open roles straight from **Greenhouse** and **Lever**, which publish every
  listing on a company's careers page as unauthenticated JSON.
- This is deliberately not scraping LinkedIn or Naukri: they block automated
  requests and forbid it in their terms. The ATS endpoints are a supported route
  and more reliable.
- Filter by role keywords, location, internship-only and remote-only. Track any
  posting into the pipeline in one click.
- Refreshed when you open the page, and a scheduled workflow wakes the free
  backend each weekday morning so the first visit of the day is not a cold start.

### Accounts

- Sign up, sign in, and everything you create stays private to your account.
- Delete your account and every resume, score and tracked application goes with
  it — the cascade is declared on the model, not swept up by a script.

## Architecture

```
                +-------------------+        +----------------------------+
   Browser ---> |  React + Vite SPA  | --/api-> |  FastAPI (Uvicorn)         |
                |  custom design sys |  HTTP  |   parsing → scoring → match  |
                +-------------------+        |   rewrite (Gemini/offline)   |
                                             |   SQLite (history)           |
                                             +----------------------------+
```

- **`frontend/`** — React 18 + Vite. Hand-built SVG gauges (no chart library),
  a custom warm-editorial design system, eight views (Dashboard, Analyze, Job
  feed, Applications, Profile, Rewrite, History, Method).
- **`backend/`** — FastAPI. Modules: `parsing.py` (PDF/DOCX extraction),
  `scoring.py` (the rubric engine), `matching.py` (TF-IDF JD matching),
  `ai.py` (Gemini + fallback), `interview.py` (gap detection and rebuild),
  `profiles.py` (resume → structured profile), `jobs.py` (posting fetch and
  field extraction), `tailor.py` (per-job resume generation),
  `coverletter.py` (per-job letters), `urgency.py` (follow-up rules),
  `jobfeed.py` (Greenhouse/Lever adapters), `documents.py` (.docx/.pdf output),
  `models.py` + `db.py` + `database.py` (schema, connection, data access),
  `auth.py` (bcrypt, JWT, throttling), `roles.py` (curated knowledge base),
  `main.py` (API).

### One design rule, applied everywhere

Every AI-assisted feature has a deterministic engine underneath it. The rules
decide *what is true*; the model only decides *how it reads*. That is why the
app still works with no API key, why nothing it writes can be fabricated, and
why every output can be explained rather than shrugged at.

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Frontend  | React 18, Vite, custom CSS design system, SVG data-viz |
| Backend   | Python, FastAPI, Pydantic, Uvicorn |
| NLP / ML  | scikit-learn (TF-IDF + cosine similarity) |
| AI        | Google Gemini (`google-generativeai`) with offline fallback |
| Parsing   | pdfplumber, python-docx |
| Storage   | SQLAlchemy ORM — PostgreSQL (Neon) in production, SQLite locally |
| Accounts  | bcrypt password hashing, PyJWT stateless sessions |
| Job feed  | Greenhouse and Lever public JSON board APIs |
| DevOps    | Docker, Docker Compose, nginx, Render / Vercel, GitHub Actions |
| Testing   | pytest — 167 tests |

## Run it locally

### Option A — two terminals (simplest for development)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # optional: add your Gemini key
uvicorn main:app --reload
```
API runs at http://localhost:8000 (interactive docs at `/docs`).

**Frontend**
```bash
cd frontend
npm install
npm run dev
```
App runs at http://localhost:5173 and proxies `/api` to the backend.

### Option B — one command with Docker

```bash
docker compose up --build
# open http://localhost:8080
```

## Configuration

Copy `backend/.env.example` to `backend/.env`:

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Free key from https://aistudio.google.com/app/apikey. Omit to use the offline rewriter. |
| `GEMINI_MODEL`   | Defaults to `gemini-1.5-flash` (free-tier friendly). |
| `PORT`           | Backend port (default 8000). |
| `DATABASE_URL`   | PostgreSQL URL. Leave blank locally to use `backend/data/radar.db`. **Required in production** — a free container's filesystem is wiped on restart. |
| `JWT_SECRET`     | Signs session tokens. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `RADAR_ENV`      | Set to `production` to make a missing `JWT_SECRET` a startup error rather than a silent fallback. |
| `ALLOWED_ORIGINS`| Comma-separated frontend origins allowed to call the API. Blank allows any, which is fine locally and too permissive once deployed. |

## Tests

```bash
cd backend
pytest
```

The tests worth reading first are `tests/test_auth.py`, which creates two
accounts and asserts the second cannot read, modify or delete the first's
applications, and `tests/test_urgency.py`, which pins the follow-up boundaries —
day six is calm, day seven is not.

## Deployment

See **[DEPLOY.md](DEPLOY.md)** for a step-by-step guide to putting RADAR live for
free (backend on Render, frontend on Vercel).

## Roadmap

- User accounts and saved resume profiles with progress tracking over time.
- Swap TF-IDF for sentence-transformer embeddings for deeper semantic matching.
- Inline, section-by-section resume editor with live re-scoring.
- Rate limiting, request logging, and observability.
- CI pipeline (GitHub Actions) running the test suite on every push.

## License

MIT — see [LICENSE](LICENSE). This is original work.
