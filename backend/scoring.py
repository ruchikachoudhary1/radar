"""
RADAR scoring engine.

A resume is graded on six independent dimensions that sum to 100. Each dimension
returns its own sub-score, a short verdict, and concrete, actionable suggestions.
The rubric is deliberately transparent so a reviewer can see *why* a resume scored
the way it did — this is the core original logic of the project.
"""
from __future__ import annotations

import re

from parsing import split_bullets
from roles import (
    EXPECTED_SECTIONS,
    ROLE_KEYWORDS,
    STRONG_ACTION_VERBS,
    WEAK_PHRASES,
)

# Weight (max points) for each rubric dimension. Sums to 100.
WEIGHTS = {
    "sections": 20,
    "role_match": 25,
    "impact": 20,
    "action_language": 15,
    "readability": 10,
    "contact": 10,
}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{8,}\d)")
LINKEDIN_RE = re.compile(r"linkedin\.com/\S+", re.I)
GITHUB_RE = re.compile(r"github\.com/\S+", re.I)
NUMBER_RE = re.compile(r"(\d+\.?\d*\s*%|\$\s*\d|\b\d{2,}\b|\b\d+x\b)", re.I)


def _band(pct: float) -> str:
    """Map a 0-1 ratio to a status band used for colour coding on the UI."""
    if pct >= 0.85:
        return "good"
    if pct >= 0.6:
        return "warning"
    if pct >= 0.35:
        return "serious"
    return "critical"


def score_sections(text: str) -> dict:
    low = text.lower()
    found, missing = [], []
    for section, aliases in EXPECTED_SECTIONS.items():
        if any(alias in low for alias in aliases):
            found.append(section)
        else:
            missing.append(section)
    ratio = len(found) / len(EXPECTED_SECTIONS)
    points = round(ratio * WEIGHTS["sections"])
    suggestions = []
    if missing:
        pretty = ", ".join(s.capitalize() for s in missing)
        suggestions.append(f"Add clearly labelled section(s): {pretty}.")
    return {
        "key": "sections",
        "label": "Structure & Sections",
        "points": points,
        "max": WEIGHTS["sections"],
        "band": _band(ratio),
        "detail": f"{len(found)} of {len(EXPECTED_SECTIONS)} expected sections detected.",
        "found": found,
        "missing": missing,
        "suggestions": suggestions,
    }


def score_role_match(text: str, role: str, jd_keywords: list[str] | None) -> dict:
    low = text.lower()
    # Prefer keywords parsed from a pasted job description; else the role bank.
    if jd_keywords:
        bank = jd_keywords
        source = "job description"
    else:
        bank = ROLE_KEYWORDS.get(role, [])
        source = f"the {role} skill bank" if role else "the selected role"

    if not bank:
        return {
            "key": "role_match",
            "label": "Role & Keyword Match",
            "points": 0,
            "max": WEIGHTS["role_match"],
            "band": "critical",
            "detail": "No target role or job description provided.",
            "matched": [],
            "missing": [],
            "suggestions": ["Select a target role or paste a job description to score keyword fit."],
        }

    matched = [kw for kw in bank if kw in low]
    missing = [kw for kw in bank if kw not in low]
    ratio = len(matched) / len(bank)
    points = round(ratio * WEIGHTS["role_match"])
    suggestions = []
    if missing:
        top_missing = ", ".join(missing[:8])
        suggestions.append(
            f"Weave in relevant missing keywords where truthful: {top_missing}."
        )
    return {
        "key": "role_match",
        "label": "Role & Keyword Match",
        "points": points,
        "max": WEIGHTS["role_match"],
        "band": _band(ratio),
        "detail": f"Matched {len(matched)} of {len(bank)} keywords from {source}.",
        "matched": matched,
        "missing": missing,
        "suggestions": suggestions,
    }


def score_impact(text: str) -> dict:
    bullets = split_bullets(text)
    total = len(bullets) or 1
    quantified = [b for b in bullets if NUMBER_RE.search(b)]
    ratio = len(quantified) / total
    points = round(ratio * WEIGHTS["impact"])
    suggestions = []
    if ratio < 0.6:
        suggestions.append(
            "Quantify more achievements — add metrics like %, time saved, users, or scale."
        )
    return {
        "key": "impact",
        "label": "Impact & Quantification",
        "points": points,
        "max": WEIGHTS["impact"],
        "band": _band(ratio),
        "detail": f"{len(quantified)} of {total} bullet lines contain measurable results.",
        "suggestions": suggestions,
    }


def score_action_language(text: str) -> dict:
    bullets = split_bullets(text)
    total = len(bullets) or 1
    low_bullets = [b.lower() for b in bullets]

    strong = sum(
        1 for b in low_bullets if b.split() and b.split()[0].strip(",.") in STRONG_ACTION_VERBS
    )
    weak_hits = [b for b in low_bullets if any(p in b for p in WEAK_PHRASES)]

    strong_ratio = strong / total
    # Weak phrases are a softer penalty than a missing strong verb.
    penalty = min(0.5 * (len(weak_hits) / total), 0.35)
    ratio = max(0.0, strong_ratio - penalty)
    points = round(ratio * WEIGHTS["action_language"])

    suggestions = []
    if weak_hits:
        suggestions.append(
            f"Replace weak openers ('worked on', 'responsible for') — found in {len(weak_hits)} line(s)."
        )
    if strong_ratio < 0.5:
        suggestions.append("Start bullets with strong verbs: Built, Led, Optimized, Shipped.")
    return {
        "key": "action_language",
        "label": "Action Language",
        "points": points,
        "max": WEIGHTS["action_language"],
        "band": _band(ratio if ratio else 0.01),
        "detail": f"{strong} strong-verb openers, {len(weak_hits)} weak phrase(s) detected.",
        "suggestions": suggestions,
    }


def score_readability(text: str) -> dict:
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    bullets = split_bullets(text)
    avg_bullet_len = (sum(len(b.split()) for b in bullets) / len(bullets)) if bullets else 0

    # Ideal: 400-800 words, average bullet 12-24 words.
    length_ok = 400 <= word_count <= 900
    bullet_ok = 8 <= avg_bullet_len <= 26
    score_fraction = 0.5 * (1 if length_ok else 0.4) + 0.5 * (1 if bullet_ok else 0.4)
    points = round(score_fraction * WEIGHTS["readability"])

    suggestions = []
    if word_count < 400:
        suggestions.append("Resume looks thin — expand experience and projects with detail.")
    elif word_count > 900:
        suggestions.append("Tighten copy — aim for one page (~400-800 words) for early-career roles.")
    if not bullet_ok and bullets:
        suggestions.append("Keep bullets to one line each (roughly 12-24 words).")
    return {
        "key": "readability",
        "label": "Readability & Brevity",
        "points": points,
        "max": WEIGHTS["readability"],
        "band": _band(score_fraction),
        "detail": f"{word_count} words, avg bullet {avg_bullet_len:.0f} words.",
        "suggestions": suggestions,
    }


def score_contact(text: str) -> dict:
    checks = {
        "Email": bool(EMAIL_RE.search(text)),
        "Phone": bool(PHONE_RE.search(text)),
        "LinkedIn": bool(LINKEDIN_RE.search(text)),
        "GitHub": bool(GITHUB_RE.search(text)),
    }
    present = [k for k, v in checks.items() if v]
    ratio = len(present) / len(checks)
    points = round(ratio * WEIGHTS["contact"])
    missing = [k for k, v in checks.items() if not v]
    suggestions = []
    if missing:
        suggestions.append(f"Add missing contact/links: {', '.join(missing)}.")
    return {
        "key": "contact",
        "label": "Contact & Links",
        "points": points,
        "max": WEIGHTS["contact"],
        "band": _band(ratio),
        "detail": f"{len(present)} of {len(checks)} contact signals present.",
        "present": present,
        "missing": missing,
        "suggestions": suggestions,
    }


def grade(text: str, role: str = "", jd_keywords: list[str] | None = None) -> dict:
    """Run the full rubric and return the aggregate report."""
    dimensions = [
        score_sections(text),
        score_role_match(text, role, jd_keywords),
        score_impact(text),
        score_action_language(text),
        score_readability(text),
        score_contact(text),
    ]
    overall = sum(d["points"] for d in dimensions)
    overall_max = sum(d["max"] for d in dimensions)

    if overall >= 85:
        grade_letter, verdict = "A", "Strong — interview-ready with minor polish."
    elif overall >= 70:
        grade_letter, verdict = "B", "Solid — a few targeted fixes will lift it."
    elif overall >= 55:
        grade_letter, verdict = "C", "Average — several sections need work."
    else:
        grade_letter, verdict = "D", "Needs significant rework before applying."

    # Flatten the top suggestions across dimensions, weakest dimensions first.
    ordered = sorted(dimensions, key=lambda d: d["points"] / d["max"])
    top_fixes = []
    for d in ordered:
        for s in d["suggestions"]:
            top_fixes.append({"area": d["label"], "text": s})

    return {
        "overall": overall,
        "overall_max": overall_max,
        "grade": grade_letter,
        "verdict": verdict,
        "band": _band(overall / overall_max),
        "dimensions": dimensions,
        "top_fixes": top_fixes[:6],
    }
