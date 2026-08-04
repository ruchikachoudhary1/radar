"""
Per-application resume tailoring.

Takes the stored master profile plus a parsed job description and produces a
resume aimed at that specific posting. Same two-layer contract as ai.py and
interview.py: Gemini writes it when a key is configured, and a deterministic
rule engine produces a usable resume when it isn't.

The rule layer never invents content. It reorders and re-emphasises what the
profile already contains — leading with the skills the posting actually asks
for — because a tracker that quietly fabricates experience is worse than one
that produces a plain resume.
"""
from __future__ import annotations

import os
import re

import ai
import matching
import profiles

TAILOR_PROMPT = """You are an expert résumé writer. Write a résumé for this candidate \
targeting the specific job below.

HARD RULES:
- Use ONLY facts present in the candidate profile. Never invent employers, dates, \
degrees, numbers or technologies the candidate did not list.
- Where the profile lacks a metric, write a clearly marked [add metric] placeholder.
- Lead with the skills and experience this posting actually asks for; drop or demote \
anything irrelevant to it.
- Start every achievement bullet with a strong past-tense verb. One line each, under \
24 words, no pronouns.
- Mirror the posting's own vocabulary where the candidate genuinely has that skill, \
so it passes keyword screening.
- Output PLAIN TEXT only. Section headings in UPPERCASE on their own line. Bullets \
start with "- ".
- Order: name/contact block, SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION, extras.
- No markdown, no commentary — just the résumé.

TARGET JOB
Title: {title}
Company: {company}
Description:
{jd}

CANDIDATE PROFILE
{profile}
"""


def _gemini_tailor(profile_text: str, jd_text: str, title: str, company: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        resp = model.generate_content(
            TAILOR_PROMPT.format(
                title=title or "the advertised role",
                company=company or "the company",
                jd=jd_text[:6000],
                profile=profile_text,
            )
        )
        out = _strip_fences(resp.text)
        return out if len(out.split()) > 60 else ""
    except Exception:
        return ""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _rank_skills(skills: list[str], keywords: list[str]) -> tuple[list[str], list[str]]:
    """Sort the profile's skills so posting-relevant ones lead. Returns (ranked, hits)."""
    keyset = [k.lower() for k in keywords]
    hits, rest = [], []
    for skill in skills:
        low = skill.lower()
        if any(k in low or low in k for k in keyset):
            hits.append(skill)
        else:
            rest.append(skill)
    return hits + rest, hits


def _rule_tailor(profile: dict, jd_text: str, meta: dict, keywords: list[str]) -> str:
    """Deterministic tailoring: re-emphasise, never fabricate."""
    tuned = dict(profile)
    ranked, hits = _rank_skills(profile.get("skills", []), keywords)
    tuned["skills"] = ranked

    title = meta.get("title") or ""
    company = meta.get("company") or ""

    # A targeted opening line, built only from facts we already hold.
    target = f"Targeting the {title} role" if title else "Targeting this role"
    if company:
        target += f" at {company}"
    if hits:
        target += f", with hands-on experience in {', '.join(hits[:6])}"
    target += "."

    existing = (profile.get("summary") or "").strip()
    tuned["summary"] = f"{target}\n{existing}" if existing else target

    return profiles.render(tuned)


def tailor(profile: dict, jd_text: str, meta: dict | None = None) -> dict:
    """
    Build a resume for one specific posting.

    Returns the resume text, which engine wrote it, and the keyword coverage of
    the result against the posting so the UI can show a match score.
    """
    meta = meta or {}
    profile_text = profiles.render(profile)
    keywords = matching.jd_keywords(jd_text) if jd_text.strip() else []

    resume_text, engine = "", "rule-based"
    if ai.gemini_available() and jd_text.strip():
        resume_text = _gemini_tailor(
            profile_text, jd_text, meta.get("title", ""), meta.get("company", "")
        )
        if resume_text:
            engine = "gemini"

    if not resume_text:
        resume_text = _rule_tailor(profile, jd_text, meta, keywords)

    return {
        "engine": engine,
        "resume_text": resume_text,
        "match": matching.similarity(resume_text, jd_text),
        "baseline_match": matching.similarity(profile_text, jd_text),
    }
