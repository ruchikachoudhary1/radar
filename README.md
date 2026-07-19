# RADAR — Resume Analysis & Role Alignment

RADAR is a full-stack web application that scores a resume against a target role
or a pasted job description, explains **why** it scored that way across six
weighted dimensions, and rewrites weak bullet points into strong, quantified
ones. It is built as a real product service: a typed REST API, an NLP matching
layer, a persistence layer, an optional LLM integration with a graceful offline
fallback, a test suite, and containerised deployment.

> **Live demo:** _add your deployed URL here after following DEPLOY.md_

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
- **Production shape.** Typed FastAPI backend with auto-generated OpenAPI docs,
  SQLite persistence, CORS, Dockerfiles for both services, an nginx reverse proxy,
  a Docker Compose stack, and one-click cloud deploy configs.
- **Tested.** A unit-test suite covers the scoring engine, parser, matcher and
  rewriter.

## Features

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
- Export any report to PDF (print).

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
  a custom warm-editorial design system, four views (Analyze, Rewrite, History,
  Method).
- **`backend/`** — FastAPI. Modules: `parsing.py` (PDF/DOCX extraction),
  `scoring.py` (the rubric engine), `matching.py` (TF-IDF JD matching),
  `ai.py` (Gemini + fallback), `database.py` (SQLite), `roles.py` (curated
  knowledge base), `main.py` (API).

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Frontend  | React 18, Vite, custom CSS design system, SVG data-viz |
| Backend   | Python, FastAPI, Pydantic, Uvicorn |
| NLP / ML  | scikit-learn (TF-IDF + cosine similarity) |
| AI        | Google Gemini (`google-generativeai`) with offline fallback |
| Parsing   | pdfplumber, python-docx |
| Storage   | SQLite |
| DevOps    | Docker, Docker Compose, nginx, Render / Vercel configs |
| Testing   | pytest-style unit tests |

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

## Tests

```bash
cd backend
pytest                 # or: python tests/test_scoring.py
```

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
