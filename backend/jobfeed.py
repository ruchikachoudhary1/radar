"""
Daily job feed from public applicant-tracking-system boards.

Most companies host their careers page on Greenhouse, Lever or similar, and
those platforms publish the same listings as unauthenticated JSON. Reading
those endpoints is a supported, documented route — unlike scraping LinkedIn or
Naukri, which is both against their terms and actively blocked. When a source
is unavailable the feed degrades to whatever the other boards returned rather
than failing outright.

This is a *daily refresh*, not a live feed: a scheduled job repopulates the
stored listings, and the app reads what was stored.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

TIMEOUT = 15
USER_AGENT = "RADAR/1.0 (job feed; student project)"

# A board token goes straight into the request path, so it is restricted to the
# characters real tokens actually use. Without this, a token like
# "../../something" or one containing a host would let a saved company entry
# point the fetch somewhere it was never meant to go.
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")

REMOTE_HINTS = ("remote", "anywhere", "distributed", "work from home", "wfh")
INTERN_HINTS = ("intern", "internship", "trainee", "apprentice", "co-op", "coop")


class FeedError(Exception):
    """A board could not be read. Carries a message fit to show a user."""


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise FeedError("No public job board found for that name.")
        raise FeedError(f"That board returned an error ({exc.code}).")
    except (urllib.error.URLError, TimeoutError):
        raise FeedError("Couldn't reach that board. It may be down.")
    except json.JSONDecodeError:
        raise FeedError("That board returned something we couldn't read.")


def _iso(value: str | None) -> str:
    """Normalise the various timestamps these boards use to a plain date."""
    if not value:
        return ""
    text = str(value)
    # Lever gives epoch milliseconds; Greenhouse gives ISO 8601.
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text) / 1000, timezone.utc).date().isoformat()
        except (ValueError, OSError):
            return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _looks_remote(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return any(h in blob for h in REMOTE_HINTS)


def _looks_like_internship(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return any(h in blob for h in INTERN_HINTS)


# --------------------------------------------------------------------------
# Source adapters — each returns the same normalised shape
# --------------------------------------------------------------------------
def _greenhouse(token: str) -> list[dict]:
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if not isinstance(data, dict):
        raise FeedError("That board returned something we couldn't read.")

    out = []
    for job in data.get("jobs", []):
        location = ((job.get("location") or {}).get("name") or "").strip()
        title = (job.get("title") or "").strip()
        out.append({
            "source": "greenhouse",
            "external_id": str(job.get("id") or ""),
            "company": (job.get("company_name") or token).strip(),
            "title": title,
            "location": location,
            "url": job.get("absolute_url") or "",
            "posted_at": _iso(job.get("first_published") or job.get("updated_at")),
            "remote": _looks_remote(location, title),
            "internship": _looks_like_internship(title),
        })
    return out


def _lever(token: str) -> list[dict]:
    data = _get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    # Lever answers 200 with {"ok": false} for an unknown board rather than 404.
    if isinstance(data, dict) and not data.get("ok", True):
        raise FeedError("No public job board found for that name.")
    if not isinstance(data, list):
        raise FeedError("That board returned something we couldn't read.")

    out = []
    for job in data:
        cats = job.get("categories") or {}
        location = (cats.get("location") or "").strip()
        title = (job.get("text") or "").strip()
        commitment = (cats.get("commitment") or "").strip()
        out.append({
            "source": "lever",
            "external_id": str(job.get("id") or ""),
            "company": token,
            "title": title,
            "location": location,
            "url": job.get("hostedUrl") or job.get("applyUrl") or "",
            "posted_at": _iso(job.get("createdAt")),
            "remote": _looks_remote(location, title, cats.get("workplaceType") or ""),
            "internship": _looks_like_internship(title, commitment),
        })
    return out


SOURCES = {"greenhouse": _greenhouse, "lever": _lever}


def fetch_board(source: str, token: str) -> list[dict]:
    """Read one company's open roles. Raises FeedError with a readable reason."""
    source = (source or "").strip().lower()
    token = (token or "").strip()

    if source not in SOURCES:
        raise FeedError(f"Unknown source. Use one of: {', '.join(sorted(SOURCES))}.")
    if not TOKEN_RE.match(token):
        raise FeedError("That board name contains characters we don't allow.")

    jobs = SOURCES[source](token)
    # A posting with no link is useless to the user and usually means the board
    # returned a placeholder row.
    return [j for j in jobs if j["url"] and j["title"]]


# --------------------------------------------------------------------------
# Matching against saved preferences
# --------------------------------------------------------------------------
def _any_match(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(n.strip().lower() in low for n in needles if n.strip())


def match_reasons(job: dict, prefs: dict) -> list[str]:
    """
    Why this posting is in the feed.

    Shown on the card so the feed can be argued with. A user who can see *why*
    something matched can fix their filters; one who just sees a list has to
    guess what the app is thinking.
    """
    reasons = []
    title = (job.get("title") or "").lower()
    for role in prefs.get("roles") or []:
        if role.strip() and role.strip().lower() in title:
            reasons.append(role.strip())

    if job.get("internship"):
        reasons.append("Internship")
    if job.get("remote"):
        reasons.append("Remote")
    else:
        for place in prefs.get("locations") or []:
            if place.strip() and place.strip().lower() in (job.get("location") or "").lower():
                reasons.append(place.strip())
                break
    return reasons


def matches(job: dict, prefs: dict) -> bool:
    """
    Does this posting fit what the user said they want?

    Every filter is skipped when its preference list is empty, so a user who
    has set nothing sees everything rather than nothing — an empty feed reads
    as broken, and "I haven't told it what I want yet" is not an error.
    """
    roles = prefs.get("roles") or []
    if roles and not _any_match(job.get("title", ""), roles):
        return False

    if prefs.get("internships_only") and not job.get("internship"):
        return False

    if prefs.get("remote_only") and not job.get("remote"):
        return False

    locations = prefs.get("locations") or []
    if locations and not job.get("remote"):
        if not _any_match(job.get("location", ""), locations):
            return False

    return True


def collect(companies: list[dict], prefs: dict | None = None) -> dict:
    """
    Read every saved board and return the postings that fit.

    One unreachable board must not empty the whole feed, so failures are
    collected and reported alongside the results rather than raised.
    """
    prefs = prefs or {}
    jobs: list[dict] = []
    problems: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for entry in companies:
        source = entry.get("source", "greenhouse")
        token = entry.get("token", "")
        try:
            for job in fetch_board(source, token):
                key = (job["source"], job["external_id"])
                if key in seen:
                    continue
                seen.add(key)
                if matches(job, prefs):
                    if entry.get("label"):
                        job["company"] = entry["label"]
                    job["reasons"] = match_reasons(job, prefs)
                    jobs.append(job)
        except FeedError as exc:
            problems.append({"source": source, "token": token, "error": str(exc)})

    jobs.sort(key=lambda j: j.get("posted_at") or "", reverse=True)
    return {"jobs": jobs, "problems": problems}
