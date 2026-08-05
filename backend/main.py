"""
RADAR — Resume Analysis & Role Alignment
FastAPI backend exposing the analysis, matching and rewriting services.
"""
from __future__ import annotations

import io
import os
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import ai
import auth
import coverletter
import database
import db as db_module
import documents
import interview
import jobfeed
import jobs
import matching
import parsing
import profiles
import scoring
import tailor
from auth import current_user, get_db
from models import User
from roles import ROLE_KEYWORDS

load_dotenv()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables and apply column migrations once, at startup."""
    database.init_db()
    yield


app = FastAPI(title="RADAR API", version="2.0.0", lifespan=lifespan)

# In production, restrict to the deployed frontend so a hostile page cannot
# call this API with a user's token. ALLOWED_ORIGINS is a comma-separated list.
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)




class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class RewriteRequest(BaseModel):
    bullet: str
    variants: int = 3


class QuestionsRequest(BaseModel):
    analysis_id: int


class BuildRequest(BaseModel):
    analysis_id: int
    answers: dict[str, str]


class ExportRequest(BaseModel):
    text: str
    format: str = "docx"
    filename: str = "resume"


class ProfileFromAnalysis(BaseModel):
    analysis_id: int
    prefer_rebuilt: bool = True


class JobParseRequest(BaseModel):
    url: str = ""
    text: str = ""


class ApplicationCreate(BaseModel):
    url: str = ""
    text: str = ""
    company: str = ""
    title: str = ""
    job_type: str = ""
    work_mode: str = ""
    location: str = ""
    stipend: str = ""
    duration: str = ""
    status: str = "Saved"
    notes: str = ""
    jd_text: str = ""
    deadline: str = ""
    generate_resume: bool = True


class ApplicationPatch(BaseModel):
    company: str | None = None
    title: str | None = None
    url: str | None = None
    job_type: str | None = None
    work_mode: str | None = None
    location: str | None = None
    stipend: str | None = None
    duration: str | None = None
    status: str | None = None
    notes: str | None = None
    resume_text: str | None = None
    deadline: str | None = None
    replied: bool | None = None


class SavedBoard(BaseModel):
    source: str = "greenhouse"
    token: str = ""
    label: str = ""


class PreferencesUpdate(BaseModel):
    roles: list[str] = []
    locations: list[str] = []
    companies: list[SavedBoard] = []
    internships_only: bool = False
    remote_only: bool = False


class BoardCheck(BaseModel):
    source: str = "greenhouse"
    token: str = ""


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": ai.gemini_available(),
        # Names the storage backend so a missing DATABASE_URL is visible rather
        # than silently falling back to a file that the next restart wipes.
        "storage": "postgres" if db_module.is_postgres() else "sqlite",
        "roles": list(ROLE_KEYWORDS.keys()),
    }


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------
@app.post("/api/auth/signup")
def signup(req: SignupRequest, db: Session = Depends(get_db)) -> dict:
    email, password = auth.validate_credentials(req.email, req.password)
    if auth.find_by_email(db, email):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        email=email,
        password_hash=auth.hash_password(password),
        name=(req.name or "").strip(),
    )
    db.add(user)
    db.commit()
    return {"token": auth.create_token(user.id), "user": auth.public_user(user)}


@app.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> dict:
    # Throttle per email rather than per IP: an attacker can rotate addresses
    # far more easily than they can guess which account they want.
    key = (req.email or "").strip().lower()
    auth.check_not_locked_out(key)

    user = auth.find_by_email(db, key)
    # One message for both branches: saying which half was wrong tells an
    # attacker whether an email is registered.
    if not user or not auth.verify_password(req.password or "", user.password_hash):
        auth.record_failure(key)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    auth.clear_failures(key)
    return {"token": auth.create_token(user.id), "user": auth.public_user(user)}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": auth.public_user(user)}


@app.delete("/api/auth/me")
def delete_account(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """
    Delete the account and everything in it.

    The cascades are declared on the User relationships, so removing the row
    takes the profile, analyses and applications with it rather than leaving
    orphaned resumes behind.
    """
    email = user.email
    db.delete(user)
    db.commit()
    auth.clear_failures(email)
    return {"deleted": True}


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    role: str = Form(""),
    job_description: str = Form(""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    text = parsing.extract_text(file.filename, data)
    if len(text.split()) < 30:
        raise HTTPException(
            status_code=422,
            detail="Could not extract enough text. Is this a text-based (not scanned) resume?",
        )

    jd_keywords = matching.jd_keywords(job_description) if job_description.strip() else None
    report = scoring.grade(text, role=role, jd_keywords=jd_keywords)
    report["jd_match"] = matching.similarity(text, job_description)
    report["meta"] = {
        "filename": file.filename,
        "role": role,
        "word_count": len(text.split()),
        "gemini": ai.gemini_available(),
    }

    analysis_id = database.save_analysis(db, user, file.filename, role, report, resume_text=text)
    report["id"] = analysis_id
    return report


# --------------------------------------------------------------------------
# Interactive gap-fill interview
# --------------------------------------------------------------------------
def _load_analysis(db: Session, user: User, analysis_id: int) -> dict:
    record = database.get_analysis(db, user, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="That analysis no longer exists.")
    if not record.get("resume_text"):
        raise HTTPException(
            status_code=409,
            detail="This analysis predates the interview feature. Re-upload the resume to continue.",
        )
    return record


@app.post("/api/interview/questions")
def interview_questions(
    req: QuestionsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Work out what's missing from a scored resume and ask about it."""
    record = _load_analysis(db, user, req.analysis_id)
    result = interview.build_questions(
        record["resume_text"], record["report"], record.get("role") or ""
    )
    database.save_questions(db, user, req.analysis_id, result["questions"])
    result["analysis_id"] = req.analysis_id
    return result


@app.post("/api/interview/build")
def interview_build(
    req: BuildRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Fold the answers back in, then re-score the rebuilt resume."""
    record = _load_analysis(db, user, req.analysis_id)
    questions = record.get("questions") or []
    if not questions:
        raise HTTPException(
            status_code=409, detail="Generate the questions before submitting answers."
        )

    role = record.get("role") or ""
    result = interview.rebuild(record["resume_text"], questions, req.answers, role)
    new_text = result["resume_text"]

    # Re-grade the ORIGINAL with the same parameters as the rebuild, so the
    # before/after delta compares like with like (the stored report may have
    # been scored against a pasted job description instead of the role bank).
    before = scoring.grade(record["resume_text"], role=role)
    after = scoring.grade(new_text, role=role)
    database.save_rebuild(db, user, req.analysis_id, req.answers, new_text)

    result["analysis_id"] = req.analysis_id
    result["score_before"] = before["overall"]
    result["score_after"] = after["overall"]
    result["grade_before"] = before["grade"]
    result["grade_after"] = after["grade"]
    result["report_after"] = after
    return result


@app.post("/api/export")
def export(req: ExportRequest, user: User = Depends(current_user)):
    """Download a resume as a formatted .docx or .pdf."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Nothing to export.")

    fmt = req.format.lower()
    if fmt == "docx":
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        try:
            payload = documents.to_docx(req.text)
        except ImportError:
            raise HTTPException(status_code=501, detail="python-docx is not installed on the server.")
    elif fmt == "pdf":
        media = "application/pdf"
        try:
            payload = documents.to_pdf(req.text)
        except ImportError:
            raise HTTPException(status_code=501, detail="fpdf2 is not installed on the server.")
    elif fmt == "txt":
        media, payload = "text/plain; charset=utf-8", req.text.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Format must be docx, pdf or txt.")

    name = documents.safe_filename(req.filename, fmt)
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --------------------------------------------------------------------------
# Master profile
# --------------------------------------------------------------------------
@app.get("/api/profile")
def read_profile(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    stored = database.get_profile(db, user)
    return {
        "profile": stored or profiles.empty(),
        "exists": stored is not None,
        "usable": profiles.is_usable(stored or {}),
    }


@app.put("/api/profile")
def write_profile(
    data: dict, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    clean = profiles.normalise(data.get("profile", data))
    database.save_profile(db, user, clean)
    return {"profile": clean, "usable": profiles.is_usable(clean)}


@app.post("/api/profile/from-analysis")
def profile_from_analysis(
    req: ProfileFromAnalysis,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Seed the master profile from a resume already uploaded and scored."""
    record = _load_analysis(db, user, req.analysis_id)
    # The interview-rebuilt version is richer, so prefer it when one exists.
    source = record.get("rebuilt") if req.prefer_rebuilt else None
    clean = profiles.normalise(profiles.extract(source or record["resume_text"]))
    database.save_profile(db, user, clean)
    return {
        "profile": clean,
        "usable": profiles.is_usable(clean),
        "source": "rebuilt resume" if source else "uploaded resume",
    }


# --------------------------------------------------------------------------
# Job postings and the application tracker
# --------------------------------------------------------------------------
@app.post("/api/jobs/parse")
def parse_job(req: JobParseRequest, user: User = Depends(current_user)) -> dict:
    """Read a posting from a link or pasted text and pull out its details."""
    try:
        return jobs.ingest(url=req.url, text=req.text)
    except jobs.FetchError as exc:
        # 422 rather than 502: the UI treats this as "ask the user to paste".
        raise HTTPException(status_code=422, detail=str(exc))


def _clean_deadline(value: str | None) -> str:
    """
    Accept an empty string or a YYYY-MM-DD date, and nothing else.

    The pipeline colours a card red once the deadline has passed, so a value
    that cannot be parsed would silently never trigger. Rejecting it here
    means a bad date is a visible 400 rather than a warning that never fires.
    """
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Deadline must be a date in YYYY-MM-DD form."
        )


@app.get("/api/applications")
def list_applications(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    return {
        "items": database.list_applications(db, user),
        "statuses": list(jobs.STATUSES),
        "job_types": list(jobs.JOB_TYPES),
        "work_modes": list(jobs.WORK_MODES),
    }


@app.post("/api/applications")
def create_application(
    req: ApplicationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Add a posting to the tracker, tailoring a resume for it by default."""
    jd_text = req.jd_text.strip()
    meta = {}
    if not jd_text and (req.url.strip() or req.text.strip()):
        try:
            parsed = jobs.ingest(url=req.url, text=req.text)
        except jobs.FetchError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        jd_text = parsed["jd_text"]
        meta = parsed["meta"]

    # Anything the user typed on the form wins over what the parser guessed.
    record = {
        field: (getattr(req, field, "") or meta.get(field, "") or "")
        for field in ("company", "title", "job_type", "work_mode",
                      "location", "stipend", "duration")
    }
    record.update({
        "url": req.url.strip(),
        "status": req.status or "Saved",
        "notes": req.notes,
        "jd_text": jd_text,
        "deadline": _clean_deadline(req.deadline),
    })

    if req.generate_resume:
        stored = database.get_profile(db, user)
        if not profiles.is_usable(stored or {}):
            raise HTTPException(
                status_code=409,
                detail="Set up your profile first — the tracker builds each resume from it.",
            )
        result = tailor.tailor(stored, jd_text, record)
        record["resume_text"] = result["resume_text"]
        record["engine"] = result["engine"]
        record["match_score"] = (result["match"] or {}).get("score")

    app_id = database.create_application(db, user, record)
    return database.get_application(db, user, app_id)


@app.get("/api/applications/{app_id}")
def read_application(
    app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    record = database.get_application(db, user, app_id)
    if not record:
        raise HTTPException(status_code=404, detail="That application no longer exists.")
    return record


@app.patch("/api/applications/{app_id}")
def patch_application(
    app_id: int,
    req: ApplicationPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    changes = {k: v for k, v in req.model_dump().items() if v is not None}
    if changes.get("status") and changes["status"] not in jobs.STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Status must be one of: {', '.join(jobs.STATUSES)}."
        )
    if "deadline" in changes:
        changes["deadline"] = _clean_deadline(changes["deadline"])
    if not database.update_application(db, user, app_id, changes):
        raise HTTPException(status_code=404, detail="That application no longer exists.")
    return database.get_application(db, user, app_id)


@app.post("/api/applications/{app_id}/tailor")
def retailor_application(
    app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """Rebuild this application's resume from the current profile."""
    record = database.get_application(db, user, app_id)
    if not record:
        raise HTTPException(status_code=404, detail="That application no longer exists.")

    stored = database.get_profile(db, user)
    if not profiles.is_usable(stored or {}):
        raise HTTPException(
            status_code=409,
            detail="Set up your profile first — the tracker builds each resume from it.",
        )

    result = tailor.tailor(stored, record.get("jd_text") or "", record)
    database.update_application(db, user, app_id, {
        "resume_text": result["resume_text"],
        "engine": result["engine"],
        "match_score": (result["match"] or {}).get("score"),
    })
    result["application"] = database.get_application(db, user, app_id)
    return result


@app.post("/api/applications/{app_id}/cover-letter")
def write_cover_letter(
    app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """Write (or rewrite) the cover letter for this application."""
    record = database.get_application(db, user, app_id)
    if not record:
        raise HTTPException(status_code=404, detail="That application no longer exists.")

    stored = database.get_profile(db, user)
    if not profiles.is_usable(stored or {}):
        raise HTTPException(
            status_code=409,
            detail="Set up your profile first — the letter is written from it.",
        )

    result = coverletter.write(stored, record.get("jd_text") or "", record)
    database.update_application(db, user, app_id, {"cover_letter": result["letter_text"]})
    result["application"] = database.get_application(db, user, app_id)
    return result


@app.delete("/api/applications/{app_id}")
def remove_application(
    app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    if not database.delete_application(db, user, app_id):
        raise HTTPException(status_code=404, detail="That application no longer exists.")
    return {"deleted": app_id}


@app.post("/api/rewrite")
def rewrite(req: RewriteRequest, user: User = Depends(current_user)) -> dict:
    if not req.bullet.strip():
        raise HTTPException(status_code=400, detail="Provide a bullet to rewrite.")
    return ai.rewrite_bullet(req.bullet, n=max(1, min(req.variants, 5)))


@app.get("/api/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    return {"items": database.list_history(db, user)}


# --------------------------------------------------------------------------
# Job feed
# --------------------------------------------------------------------------
@app.get("/api/preferences")
def read_preferences(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    return {"preferences": database.get_preferences(db, user), "sources": sorted(jobfeed.SOURCES)}


@app.put("/api/preferences")
def write_preferences(
    req: PreferencesUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    data = req.model_dump()
    # Validate every saved board up front. A bad token would otherwise fail
    # silently on each refresh, and the user would just see an empty feed.
    for entry in data["companies"]:
        source = (entry.get("source") or "").lower()
        if source not in jobfeed.SOURCES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source '{entry.get('source')}'. "
                       f"Use one of: {', '.join(sorted(jobfeed.SOURCES))}.",
            )
        if not jobfeed.TOKEN_RE.match((entry.get("token") or "").strip()):
            raise HTTPException(
                status_code=400,
                detail=f"'{entry.get('token')}' isn't a valid board name.",
            )
    return {"preferences": database.save_preferences(db, user, data)}


@app.post("/api/feed/check")
def check_board(req: BoardCheck, user: User = Depends(current_user)) -> dict:
    """Confirm a board exists before the user saves it."""
    try:
        jobs = jobfeed.fetch_board(req.source, req.token)
    except jobfeed.FeedError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "ok": True,
        "count": len(jobs),
        "company": jobs[0]["company"] if jobs else req.token,
    }


@app.get("/api/feed")
def job_feed(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """
    Today's matching postings from the user's saved boards.

    Fetched on request rather than served from a cache table: the volume is a
    handful of boards, and a stale feed is worse than a slow one. The daily
    GitHub Actions ping exists to keep the container awake, not to build this.
    """
    prefs = database.get_preferences(db, user)
    if not prefs.get("companies"):
        return {"jobs": [], "problems": [], "configured": False, "preferences": prefs}

    result = jobfeed.collect(prefs["companies"], prefs)
    database.stamp_feed_refresh(db, user)

    # Mark anything already in the tracker so the user is not offered a job
    # they have already filed.
    tracked = {
        (a.get("url") or "").strip()
        for a in database.list_applications(db, user)
        if a.get("url")
    }
    for job in result["jobs"]:
        job["tracked"] = job["url"] in tracked

    result["configured"] = True
    result["preferences"] = database.get_preferences(db, user)
    return result


@app.get("/api/summary")
def summary(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Everything the dashboard shows, in one request."""
    return database.summarise(db, user)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
