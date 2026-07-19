"""
RADAR — Resume Analysis & Role Alignment
FastAPI backend exposing the analysis, matching and rewriting services.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ai
import database
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

    analysis_id = database.save_analysis(file.filename, role, report)
    report["id"] = analysis_id
    return report


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
