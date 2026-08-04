"""
RADAR — Resume Analysis & Role Alignment
FastAPI backend exposing the analysis, matching and rewriting services.
"""
from __future__ import annotations

import io
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import ai
import database
import documents
import interview
import matching
import parsing
import scoring
from roles import ROLE_KEYWORDS

load_dotenv()

app = FastAPI(title="RADAR API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    database.init_db()


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


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "gemini_configured": ai.gemini_available(),
        "roles": list(ROLE_KEYWORDS.keys()),
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    role: str = Form(""),
    job_description: str = Form(""),
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

    analysis_id = database.save_analysis(file.filename, role, report, resume_text=text)
    report["id"] = analysis_id
    return report


# --------------------------------------------------------------------------
# Interactive gap-fill interview
# --------------------------------------------------------------------------
def _load_analysis(analysis_id: int) -> dict:
    record = database.get_analysis(analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="That analysis no longer exists.")
    if not record.get("resume_text"):
        raise HTTPException(
            status_code=409,
            detail="This analysis predates the interview feature. Re-upload the resume to continue.",
        )
    return record


@app.post("/api/interview/questions")
def interview_questions(req: QuestionsRequest) -> dict:
    """Work out what's missing from a scored resume and ask about it."""
    record = _load_analysis(req.analysis_id)
    result = interview.build_questions(
        record["resume_text"], record["report"], record.get("role") or ""
    )
    database.save_questions(req.analysis_id, result["questions"])
    result["analysis_id"] = req.analysis_id
    return result


@app.post("/api/interview/build")
def interview_build(req: BuildRequest) -> dict:
    """Fold the answers back in, then re-score the rebuilt resume."""
    record = _load_analysis(req.analysis_id)
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
    database.save_rebuild(req.analysis_id, req.answers, new_text)

    result["analysis_id"] = req.analysis_id
    result["score_before"] = before["overall"]
    result["score_after"] = after["overall"]
    result["grade_before"] = before["grade"]
    result["grade_after"] = after["grade"]
    result["report_after"] = after
    return result


@app.post("/api/export")
def export(req: ExportRequest):
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


@app.post("/api/rewrite")
def rewrite(req: RewriteRequest) -> dict:
    if not req.bullet.strip():
        raise HTTPException(status_code=400, detail="Provide a bullet to rewrite.")
    return ai.rewrite_bullet(req.bullet, n=max(1, min(req.variants, 5)))


@app.get("/api/history")
def history() -> dict:
    return {"items": database.list_history()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
