"""
Cover letter generation.

Same two-layer contract as the rest of the app: Gemini writes it when a key is
configured, and a deterministic template writes a usable letter when it isn't.

The rule layer never invents anything. It states which of the posting's asks
the candidate genuinely matches, drawn from the profile's own skill list, and
leaves a marked placeholder wherever a specific the writer cannot know belongs.
A letter that quietly claims the wrong degree or the wrong years is worse than
a plain one the candidate finishes themselves.
"""
from __future__ import annotations

import os
import re

import ai
import matching

LETTER_PROMPT = """You are an expert cover letter writer. Write a cover letter for this \
candidate targeting the specific job below.

HARD RULES:
- Use ONLY facts present in the candidate profile. Never invent employers, dates, \
degrees, numbers, or technologies the candidate did not list.
- Where a specific would strengthen a claim but the profile does not contain it, write \
a clearly marked [add detail] placeholder rather than inventing one.
- Three or four short paragraphs. Under 320 words total.
- Open with the specific role and why this candidate fits it — no "I am writing to \
apply for".
- Middle paragraphs: connect the candidate's actual experience to what the posting \
asks for. Concrete, not adjectival.
- Close with a direct, unfussy line about next steps.
- No flattery about the company being "innovative" or "industry-leading".
- Plain text only. No markdown, no subject line, no letterhead, no commentary.

TARGET JOB
Title: {title}
Company: {company}
Description:
{jd}

CANDIDATE PROFILE
{profile}
"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _gemini_letter(profile_text: str, jd_text: str, title: str, company: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        resp = model.generate_content(
            LETTER_PROMPT.format(
                title=title or "the advertised role",
                company=company or "the company",
                jd=jd_text[:6000],
                profile=profile_text,
            )
        )
        out = _strip_fences(resp.text)
        # Too short means the model returned a refusal or a fragment.
        return out if len(out.split()) > 80 else ""
    except Exception:
        return ""


def _matched_skills(profile: dict, keywords: list[str], limit: int = 6) -> list[str]:
    """The candidate's own skills that this posting actually asks for."""
    keyset = [k.lower() for k in keywords]
    hits = []
    for skill in profile.get("skills", []):
        low = skill.lower()
        if any(k in low or low in k for k in keyset):
            hits.append(skill)
    return hits[:limit]


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _rule_letter(profile: dict, meta: dict, keywords: list[str]) -> str:
    """A deterministic letter built only from what the profile already says."""
    name = (profile.get("name") or "").strip()
    title = (meta.get("title") or "").strip()
    company = (meta.get("company") or "").strip()
    hits = _matched_skills(profile, keywords)

    role_phrase = f"the {title} role" if title else "this role"
    at_company = f" at {company}" if company else ""

    paras = []

    # Opening: the role, and the overlap we can actually evidence.
    if hits:
        paras.append(
            f"I'd like to be considered for {role_phrase}{at_company}. "
            f"The posting asks for {_join(hits)}, which is where most of my work "
            f"so far has been."
        )
    else:
        paras.append(
            f"I'd like to be considered for {role_phrase}{at_company}. "
            f"[add detail: one line on why this role in particular]"
        )

    # Middle: lead with whatever substance the profile actually holds.
    experience = (profile.get("experience") or "").strip()
    projects = (profile.get("projects") or "").strip()
    body = experience or projects
    if body:
        first = [ln.strip(" -•\t") for ln in body.splitlines() if ln.strip()][:2]
        if first:
            paras.append(
                "Most relevant to this posting: "
                + "; ".join(first)
                + ". [add detail: the outcome or number that made this matter]"
            )
    else:
        paras.append(
            "[add detail: two or three sentences on the work that best matches this posting]"
        )

    summary = (profile.get("summary") or "").strip()
    if summary:
        paras.append(summary)

    # Close: plain, no flourish.
    paras.append(
        "I'd welcome the chance to talk through how I'd approach the work. "
        "Thank you for your time."
    )

    letter = "\n\n".join(paras)
    if name:
        letter += f"\n\n{name}"
    return letter


def write(profile: dict, jd_text: str, meta: dict | None = None) -> dict:
    """
    Write a cover letter for one posting.

    Returns the letter, which engine produced it, and whether any placeholder
    still needs the candidate's attention before sending.
    """
    import profiles  # imported here to avoid a circular import at module load

    meta = meta or {}
    profile_text = profiles.render(profile)
    keywords = matching.jd_keywords(jd_text) if jd_text.strip() else []

    letter, engine = "", "rule-based"
    if ai.gemini_available() and jd_text.strip():
        letter = _gemini_letter(
            profile_text, jd_text, meta.get("title", ""), meta.get("company", "")
        )
        if letter:
            engine = "gemini"

    if not letter:
        letter = _rule_letter(profile, meta, keywords)

    return {
        "engine": engine,
        "letter_text": letter,
        # Both engines are instructed to mark gaps rather than invent facts, so
        # the UI can tell the user there is something left to fill in.
        "placeholders": len(re.findall(r"\[add [^\]]+\]", letter)),
        "word_count": len(letter.split()),
    }
