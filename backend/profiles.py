"""
RADAR master profile.

The application tracker needs the candidate's facts in a structured form, so a
tailored resume can be assembled for any job without re-uploading a file. This
module turns resume plain text into that structure and renders it back out.

Parsing is deliberately rule-based and conservative. A wrong guess surfaces as
an editable field in the UI, which is far safer than silently inventing one.
"""
from __future__ import annotations

import re

from scoring import EMAIL_RE, GITHUB_RE, LINKEDIN_RE, PHONE_RE

# Canonical section -> the headings a resume might actually use for it.
SECTION_ALIASES = {
    "summary": ("summary", "objective", "profile", "about", "professional summary",
                "career objective", "about me"),
    "skills": ("skills", "technical skills", "technologies", "tech stack",
               "core competencies", "areas of expertise"),
    "experience": ("experience", "work experience", "employment", "internship",
                   "internships", "professional experience", "work history"),
    "projects": ("projects", "personal projects", "academic projects",
                 "selected projects", "key projects"),
    "education": ("education", "academics", "academic background",
                  "educational qualifications", "qualifications"),
    "certifications": ("certifications", "certificates", "courses", "achievements",
                       "awards", "honors", "honours", "accomplishments"),
}

# Longest aliases first so "technical skills" wins over "skills".
_LOOKUP = sorted(
    ((alias, canon) for canon, aliases in SECTION_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)

TEXT_FIELDS = ("summary", "experience", "projects", "education", "certifications")
CONTACT_FIELDS = ("name", "email", "phone", "location", "linkedin", "github")

# "Languages: Python, Java" -> we want the values, not the group label.
_SKILL_LABEL_RE = re.compile(r"^[A-Za-z /&+-]{2,30}:\s*")
_SKILL_SPLIT_RE = re.compile(r"[,;|·•]|\s{3,}")
_LOCATION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*,\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b"
)


def _is_heading(line: str) -> str | None:
    """Return the canonical section name if this line is a section heading."""
    clean = line.strip().strip(":-–—_*# ").lower()
    if not clean or len(clean.split()) > 4:
        return None
    for alias, canon in _LOOKUP:
        if clean == alias:
            return canon
    # Also accept an all-caps heading that merely contains the alias,
    # e.g. "TECHNICAL SKILLS & TOOLS".
    if line.strip() == line.strip().upper() and any(c.isalpha() for c in line):
        for alias, canon in _LOOKUP:
            if alias in clean:
                return canon
    return None


def split_sections(text: str) -> dict[str, str]:
    """Split resume text into {canonical section: body}. Unheaded text is dropped."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.split("\n"):
        canon = _is_heading(raw)
        if canon:
            current = canon
            sections.setdefault(current, [])
            continue
        if current and raw.strip():
            sections[current].append(raw.rstrip())
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def _first(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _guess_name(text: str) -> str:
    """The name is normally the first line that isn't contact detail."""
    for raw in text.split("\n")[:6]:
        line = raw.strip()
        if not line or len(line) > 60:
            continue
        if any(p.search(line) for p in (EMAIL_RE, PHONE_RE, LINKEDIN_RE, GITHUB_RE)):
            continue
        if _is_heading(line):
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w[0].isalpha() for w in words if w):
            letters = [c for c in line if c.isalpha()]
            if letters and sum(c.isdigit() for c in line) == 0:
                return line.title() if line.isupper() else line
    return ""


def _guess_location(text: str) -> str:
    head = "\n".join(text.split("\n")[:8])
    match = _LOCATION_RE.search(head)
    return match.group(0) if match else ""


def parse_skills(body: str) -> list[str]:
    """Flatten a skills section into a de-duplicated list."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in body.split("\n"):
        line = raw.strip().lstrip("•·-–—*▪◦●○»›").strip()
        if not line:
            continue
        line = _SKILL_LABEL_RE.sub("", line)
        for part in _SKILL_SPLIT_RE.split(line):
            skill = part.strip(" .")
            if not skill or len(skill) > 40:
                continue
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                out.append(skill)
    return out


def extract(text: str) -> dict:
    """Build a structured profile from resume plain text."""
    sections = split_sections(text)
    return {
        "name": _guess_name(text),
        "email": _first(EMAIL_RE, text),
        "phone": _first(PHONE_RE, text),
        "location": _guess_location(text),
        "linkedin": _first(LINKEDIN_RE, text),
        "github": _first(GITHUB_RE, text),
        "summary": sections.get("summary", ""),
        "skills": parse_skills(sections.get("skills", "")),
        "experience": sections.get("experience", ""),
        "projects": sections.get("projects", ""),
        "education": sections.get("education", ""),
        "certifications": sections.get("certifications", ""),
    }


def empty() -> dict:
    """A blank profile with every key present, for a first-time user."""
    blank = {field: "" for field in CONTACT_FIELDS}
    blank.update({field: "" for field in TEXT_FIELDS})
    blank["skills"] = []
    return blank


def normalise(data: dict) -> dict:
    """Coerce arbitrary client input into the profile shape, ignoring extras."""
    out = empty()
    for key in out:
        if key not in data or data[key] is None:
            continue
        value = data[key]
        if key == "skills":
            if isinstance(value, str):
                value = parse_skills(value)
            out[key] = [str(s).strip() for s in value if str(s).strip()]
        else:
            out[key] = str(value).strip()
    return out


def is_usable(profile: dict) -> bool:
    """Enough substance to build a resume from."""
    return bool(profile.get("name")) and bool(
        profile.get("skills") or profile.get("experience") or profile.get("projects")
    )


def render(profile: dict) -> str:
    """Render the profile back into plain-text resume form."""
    lines: list[str] = []
    if profile.get("name"):
        lines.append(profile["name"])

    contact = [profile.get(f, "") for f in ("email", "phone", "location", "linkedin", "github")]
    contact = [c for c in contact if c]
    if contact:
        lines.append(" · ".join(contact))

    def block(heading: str, body: str) -> None:
        if body and body.strip():
            lines.extend(["", heading, body.strip()])

    block("SUMMARY", profile.get("summary", ""))
    if profile.get("skills"):
        lines.extend(["", "SKILLS", ", ".join(profile["skills"])])
    block("EXPERIENCE", profile.get("experience", ""))
    block("PROJECTS", profile.get("projects", ""))
    block("EDUCATION", profile.get("education", ""))
    block("CERTIFICATIONS", profile.get("certifications", ""))

    return "\n".join(lines).strip()
