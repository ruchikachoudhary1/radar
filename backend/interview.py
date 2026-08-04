"""
RADAR interactive gap-fill interview.

After a resume is scored, this module works out *what information is missing*
that would raise the score, turns those gaps into plain-English questions, and
then folds the user's answers back into a rewritten resume.

Two-layer design, mirroring ai.py:
  1. A deterministic rule engine finds the gaps and writes baseline questions.
     This always works — no API key, no network.
  2. If Gemini is configured, it re-phrases those questions so they read like a
     human career coach asking them, and performs the final resume rewrite.
     Any failure silently falls back to layer 1.

The rule engine owns *which* gaps exist; the AI only owns *wording*. That keeps
the feature explainable — every question can be traced to a rubric dimension.
"""
from __future__ import annotations

import json
import os
import re

import ai
from parsing import split_bullets
from scoring import EMAIL_RE, GITHUB_RE, LINKEDIN_RE, NUMBER_RE, PHONE_RE
from roles import STRONG_ACTION_VERBS, WEAK_PHRASES

MAX_QUESTIONS = 8

# Human-readable prompts for each missing contact signal.
CONTACT_PROMPTS = {
    "Email": ("What professional email address should sit at the top of the resume?",
              "e.g. yug.sharma@gmail.com"),
    "Phone": ("What phone number should recruiters use?",
              "e.g. +91 98765 43210"),
    "LinkedIn": ("What's your LinkedIn profile URL?",
                 "e.g. linkedin.com/in/yugsharma"),
    "GitHub": ("What's your GitHub (or portfolio) URL?",
               "e.g. github.com/yugsharma"),
}

SECTION_PROMPTS = {
    "education": ("Describe your education — degree, college, and graduation year.",
                  "e.g. B.Tech Computer Science, XYZ Institute, 2026, CGPA 8.4"),
    "experience": ("Describe any internship or work experience: role, organisation, dates, and what you did.",
                   "If you have none, describe your biggest project as if it were a job."),
    "skills": ("List your technical skills, grouped if you can.",
               "e.g. Languages: Python, Java · Web: React, FastAPI · Tools: Git, Docker"),
    "projects": ("Describe one project you're proud of — what it does, what you built it with, and the outcome.",
                 "Include scale or results if you have them."),
    "summary": ("In one or two sentences, who are you professionally and what are you targeting?",
                "e.g. Final-year CS student targeting backend roles, focused on Python and distributed systems."),
    "certifications": ("List any certifications, courses or awards worth showing.",
                       "Leave blank if none — the section will be skipped.")
}

QUESTION_POLISH_PROMPT = """You are a résumé coach interviewing a candidate targeting a \
{role} role. Below is a JSON list of baseline questions generated from an automated résumé audit.

Rewrite each question so it sounds like a real coach speaking: specific, warm, one sentence, \
under 30 words, ending in a question mark. Keep the exact same "id" values and the same intent. \
Do NOT add, remove, merge or reorder questions.

Return ONLY a JSON array of objects with keys "id" and "question". No markdown fences.

Baseline questions:
{questions}
"""

REBUILD_PROMPT = """You are an expert résumé writer. Rewrite the résumé below into a stronger, \
ATS-friendly version targeting a {role} role.

You are given the candidate's answers to gap-filling questions. Use that new information — it is \
true and supplied by the candidate.

HARD RULES:
- Never invent facts, employers, dates, or numbers the candidate did not give you.
- If a metric is genuinely unknown, leave a clearly marked [add metric] placeholder.
- Start every achievement bullet with a strong past-tense verb.
- Keep each bullet on one line, under 24 words, no first person, no pronouns.
- Preserve real content from the original; improve its phrasing and ordering.
- Output PLAIN TEXT only. Section headings in UPPERCASE on their own line. Bullets start with "- ".
- Order: name/contact block, SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION, then any extras.
- Do not output markdown, commentary, or explanation — just the résumé.

ORIGINAL RÉSUMÉ:
{resume}

CANDIDATE'S ANSWERS:
{answers}
"""


# --------------------------------------------------------------------------
# Layer 1 — rule-based gap detection
# --------------------------------------------------------------------------
def _weak_opener(bullet: str) -> bool:
    low = bullet.lower()
    if any(p in low for p in WEAK_PHRASES):
        return True
    first = low.split()[0].strip(",.") if low.split() else ""
    return first not in STRONG_ACTION_VERBS


def _shorten(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def find_gaps(text: str, report: dict, role: str = "") -> list[dict]:
    """Return the ordered list of questions needed to strengthen this resume."""
    questions: list[dict] = []
    dims = {d["key"]: d for d in report.get("dimensions", [])}

    # --- Contact & links -------------------------------------------------
    present = {
        "Email": bool(EMAIL_RE.search(text)),
        "Phone": bool(PHONE_RE.search(text)),
        "LinkedIn": bool(LINKEDIN_RE.search(text)),
        "GitHub": bool(GITHUB_RE.search(text)),
    }
    for label, ok in present.items():
        if not ok:
            q, hint = CONTACT_PROMPTS[label]
            questions.append({
                "id": f"contact_{label.lower()}",
                "area": "Contact & Links",
                "question": q,
                "hint": hint,
                "kind": "short",
                "context": "",
                "optional": label in ("LinkedIn", "GitHub"),
                "worth": 3,
            })

    # --- Missing sections -------------------------------------------------
    for section in dims.get("sections", {}).get("missing", []):
        if section == "contact":
            continue  # already covered field-by-field above
        q, hint = SECTION_PROMPTS.get(
            section,
            (f"Your resume has no {section} section — what should go in it?", ""),
        )
        questions.append({
            "id": f"section_{section}",
            "area": "Structure & Sections",
            "question": q,
            "hint": hint,
            "kind": "long",
            "context": "",
            "optional": section in ("certifications", "summary"),
            "worth": 4,
        })

    # --- Unquantified / weak bullets --------------------------------------
    bullets = split_bullets(text)
    unquantified = [b for b in bullets if not NUMBER_RE.search(b)]
    weak = [b for b in bullets if _weak_opener(b) and b not in unquantified]

    for i, bullet in enumerate(unquantified[:3]):
        questions.append({
            "id": f"metric_{i}",
            "area": "Impact & Quantification",
            "question": (
                f'This line has no measurable result: "{_shorten(bullet)}" — '
                "what changed because of it? A number, %, time saved, or user count."
            ),
            "hint": "e.g. cut page load from 4s to 1.2s · used by 300 students · saved 6 hours a week",
            "kind": "short",
            "context": bullet,
            "optional": False,
            "worth": 5,
        })

    for i, bullet in enumerate(weak[:2]):
        questions.append({
            "id": f"verb_{i}",
            "area": "Action Language",
            "question": (
                f'This line reads passively: "{_shorten(bullet)}" — '
                "what did *you* personally build, lead or decide here?"
            ),
            "hint": "Answer with the action you owned, not the team's.",
            "kind": "short",
            "context": bullet,
            "optional": False,
            "worth": 3,
        })

    # --- Missing role keywords -------------------------------------------
    missing_kw = dims.get("role_match", {}).get("missing", [])[:6]
    if missing_kw and role:
        questions.append({
            "id": "keywords",
            "area": "Role & Keyword Match",
            "question": (
                f"A {role} posting expects these and your resume doesn't mention them: "
                f"{', '.join(missing_kw)}. Which have you actually used, and where?"
            ),
            "hint": "Only list ones you've genuinely worked with — say which project used each.",
            "kind": "long",
            "context": ", ".join(missing_kw),
            "optional": True,
            "worth": 6,
        })

    # --- Thin resume -------------------------------------------------------
    word_count = len(text.split())
    if word_count < 400:
        questions.append({
            "id": "thin",
            "area": "Readability & Brevity",
            "question": (
                f"Your resume is only ~{word_count} words, which reads as thin. "
                "What else have you built, led or won that isn't on here yet?"
            ),
            "hint": "Hackathons, open-source, coursework projects, club leadership, freelance work.",
            "kind": "long",
            "context": "",
            "optional": True,
            "worth": 4,
        })

    # Weakest rubric areas first, so the highest-value questions lead.
    order = {d["label"]: d["points"] / d["max"] for d in report.get("dimensions", [])}
    questions.sort(key=lambda q: (order.get(q["area"], 0.5), -q["worth"]))
    return questions[:MAX_QUESTIONS]


def _gemini_polish(questions: list[dict], role: str) -> list[dict]:
    """Ask Gemini to re-word the questions. Returns [] on any failure."""
    if not questions:
        return []
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        slim = [{"id": q["id"], "question": q["question"]} for q in questions]
        resp = model.generate_content(
            QUESTION_POLISH_PROMPT.format(
                role=role or "software", questions=json.dumps(slim, indent=2)
            )
        )
        data = json.loads(_strip_fences(resp.text))
        by_id = {d["id"]: d["question"] for d in data if isinstance(d, dict) and "id" in d}
        out = []
        for q in questions:
            merged = dict(q)
            if by_id.get(q["id"]):
                merged["question"] = by_id[q["id"]].strip()
            out.append(merged)
        return out
    except Exception:
        return []


def build_questions(text: str, report: dict, role: str = "") -> dict:
    base = find_gaps(text, report, role)
    if not base:
        return {"engine": "rule-based", "questions": [], "note": "No blocking gaps found."}
    if ai.gemini_available():
        polished = _gemini_polish(base, role)
        if polished:
            return {"engine": "gemini", "questions": polished}
    return {"engine": "rule-based", "questions": base}


# --------------------------------------------------------------------------
# Layer 2 — fold the answers back into the resume
# --------------------------------------------------------------------------
def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _answered(questions: list[dict], answers: dict) -> list[tuple[dict, str]]:
    pairs = []
    for q in questions:
        a = (answers.get(q["id"]) or "").strip()
        if a:
            pairs.append((q, a))
    return pairs


def _gemini_rebuild(text: str, pairs: list[tuple[dict, str]], role: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        block = "\n\n".join(
            f"Q ({q['area']}): {q['question']}\nA: {a}"
            + (f"\n[This answer refers to the existing line: \"{q['context']}\"]" if q.get("context") and q["id"].startswith(("metric_", "verb_")) else "")
            for q, a in pairs
        )
        resp = model.generate_content(
            REBUILD_PROMPT.format(role=role or "software engineering", resume=text, answers=block)
        )
        out = _strip_fences(resp.text)
        return out if len(out.split()) > 60 else ""
    except Exception:
        return ""


def _rule_rebuild(text: str, pairs: list[tuple[dict, str]]) -> tuple[str, list[dict]]:
    """
    Deterministic rebuild: patch the specific lines the answers refer to, then
    append any brand-new sections. Not as fluent as Gemini, but always available
    and every edit is traceable.
    """
    lines = text.split("\n")
    changes: list[dict] = []
    contact_adds: list[str] = []
    new_sections: list[tuple[str, str]] = []
    extras: list[str] = []

    for q, answer in pairs:
        qid = q["id"]

        if qid.startswith("contact_"):
            contact_adds.append(answer)
            changes.append({"type": "added", "area": q["area"], "text": answer})

        elif qid.startswith("section_"):
            name = qid.split("_", 1)[1].upper()
            new_sections.append((name, answer))
            changes.append({"type": "section", "area": q["area"], "text": f"Added {name} section"})

        elif qid.startswith(("metric_", "verb_")):
            target = q.get("context", "")
            patched = _merge_metric(target, answer)
            for i, line in enumerate(lines):
                if target and target in line:
                    lines[i] = line.replace(target, patched)
                    changes.append({
                        "type": "rewritten", "area": q["area"],
                        "before": target, "after": patched,
                    })
                    break

        else:  # keywords, thin, anything else -> additional material
            extras.append(answer)
            changes.append({"type": "added", "area": q["area"], "text": _shorten(answer, 120)})

    out = lines

    if contact_adds:
        # Contact details belong in the first few lines, under the name.
        insert_at = 1 if out and out[0].strip() else 0
        out = out[:insert_at] + [" · ".join(contact_adds)] + out[insert_at:]

    for name, body in new_sections:
        out += ["", name, ""] + _as_bullets(body)

    if extras:
        out += ["", "ADDITIONAL"] + _as_bullets(" ".join(extras))

    return "\n".join(out).strip(), changes


def _merge_metric(bullet: str, answer: str) -> str:
    """Attach a supplied result to an existing bullet, leading with a strong verb."""
    core = ai._rule_rewrite(bullet, 1)
    core = core[0] if core else bullet
    core = core.rstrip(" .")
    ans = answer.strip().rstrip(".")
    if not ans:
        return core
    # If the answer already reads like a clause, join it; else label it as a result.
    joiner = ", " if ans[0].islower() else " — "
    return f"{core}{joiner}{ans}"


def _as_bullets(body: str) -> list[str]:
    """Split a free-text answer into resume bullet lines."""
    parts = [p.strip() for p in re.split(r"[\n;]|(?<=[a-z0-9])\.\s+", body) if p.strip()]
    return [f"- {p.rstrip('.')}" for p in parts] or [f"- {body.strip()}"]


def rebuild(text: str, questions: list[dict], answers: dict, role: str = "") -> dict:
    """Produce the improved resume from the interview answers."""
    pairs = _answered(questions, answers)
    if not pairs:
        return {"engine": "none", "resume_text": text, "changes": [],
                "note": "No answers supplied — resume returned unchanged."}

    if ai.gemini_available():
        rewritten = _gemini_rebuild(text, pairs, role)
        if rewritten:
            return {
                "engine": "gemini",
                "resume_text": rewritten,
                "changes": [
                    {"type": "applied", "area": q["area"], "text": _shorten(a, 120)}
                    for q, a in pairs
                ],
            }

    rewritten, changes = _rule_rebuild(text, pairs)
    return {"engine": "rule-based", "resume_text": rewritten, "changes": changes}
