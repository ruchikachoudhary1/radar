"""
Job posting ingestion.

Given a posting URL, fetch the page and reduce it to plain text; given pasted
text, use it directly. Either way the result is run through a rule-based
extractor that pulls out the facts the tracker files jobs by: company, title,
pay, location, work mode, duration, and whether it's an internship or a job.

Many large boards (LinkedIn, Indeed, Internshala) serve their postings from
JavaScript or block non-browser clients outright. That is expected, not a bug:
`fetch` raises FetchError with a readable message and the UI falls back to
asking the user to paste the description.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 2_000_000
TIMEOUT = 12
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

JOB_TYPES = ("Internship", "Full-time", "Part-time", "Contract")
WORK_MODES = ("Remote", "Hybrid", "On-site")
STATUSES = ("Saved", "Applied", "Interviewing", "Offer", "Rejected")


class FetchError(RuntimeError):
    """The posting could not be retrieved — the caller should ask for pasted text."""


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def _assert_public(url: str) -> None:
    """
    Refuse to fetch private, loopback or link-local addresses.

    The URL comes from the browser and the fetch runs server-side, so without
    this check the deployed backend would happily proxy requests to its own
    internal network or a cloud metadata endpoint.
    """
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise FetchError("Only http:// and https:// links can be opened.")
    if not parts.hostname:
        raise FetchError("That doesn't look like a valid link.")
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror:
        raise FetchError(f"Couldn't find the site '{parts.hostname}'. Check the link.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("That link points to a private address, so it can't be opened.")


def fetch(url: str) -> tuple[str, str]:
    """
    Download a posting; return (visible text, raw html).

    The html is kept because <title> is often the cleanest source of the role
    and company names once the body has been flattened. Raises FetchError.
    """
    url = url.strip()
    if not url:
        raise FetchError("No link supplied.")
    if not urllib.parse.urlparse(url).scheme:
        url = "https://" + url
    _assert_public(url)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read(MAX_BYTES)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise FetchError(
                f"{urllib.parse.urlparse(url).hostname} blocked the request "
                f"({exc.code}). Paste the job description instead."
            )
        raise FetchError(f"The site returned an error ({exc.code}).")
    except (urllib.error.URLError, socket.timeout, TimeoutError):
        raise FetchError("Couldn't reach that link — it may be slow or offline.")

    html = raw.decode(charset, errors="ignore")
    text = html_to_text(html)
    if len(text.split()) < 40:
        raise FetchError(
            "That page loads its content with JavaScript, so there's nothing to read. "
            "Paste the job description instead."
        )
    return text, html


_SCRIPT_RE = re.compile(r"<(script|style|noscript|svg|head)\b.*?</\1>", re.S | re.I)
_BREAK_RE = re.compile(r"<(br|/p|/div|/li|/h[1-6]|/tr)\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&rsquo;": "'", "&ndash;": "-", "&mdash;": "—",
}


def html_to_text(html: str) -> str:
    """Strip markup to readable text without pulling in a parser dependency."""
    text = _SCRIPT_RE.sub(" ", html)
    text = _BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------
_STIPEND_RE = re.compile(
    r"(?:₹|rs\.?|inr|\$|usd|€|£)\s?\d[\d,]*(?:\.\d+)?\s?"
    r"(?:k|lpa|lakh|lakhs|cr|crore|million|m)?"
    r"(?:\s?(?:-|–|to)\s?(?:₹|rs\.?|inr|\$|usd|€|£)?\s?\d[\d,]*(?:\.\d+)?\s?"
    r"(?:k|lpa|lakh|lakhs|cr|crore|million|m)?)?"
    r"(?:\s?(?:/|per\s)\s?(?:month|year|annum|hour|week|mo|yr))?",
    re.I,
)
_UNPAID_RE = re.compile(r"\bunpaid\b|\bno stipend\b", re.I)
_DURATION_RE = re.compile(
    r"\b(\d{1,2})\s?(?:-|–|to)?\s?(\d{1,2})?\s?(month|months|week|weeks|year|years)\b", re.I
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
# Page titles read "Role - Company | Board"; every separator splits the same way.
_TITLE_SPLIT_RE = re.compile(r"\s[|·–—-]\s|\sat\s|\s•\s")

_MODE_PATTERNS = (
    ("Remote", re.compile(r"\b(fully remote|work from home|wfh|remote)\b", re.I)),
    ("Hybrid", re.compile(r"\bhybrid\b", re.I)),
    ("On-site", re.compile(r"\b(on-?site|in-?office|in person|work from office)\b", re.I)),
)

_TYPE_PATTERNS = (
    ("Internship", re.compile(r"\b(intern|internship|trainee|apprentice)\b", re.I)),
    ("Contract", re.compile(r"\b(contract|freelance|consultant)\b", re.I)),
    ("Part-time", re.compile(r"\bpart[- ]time\b", re.I)),
    ("Full-time", re.compile(r"\b(full[- ]time|permanent)\b", re.I)),
)

_ROLE_WORDS = (
    "engineer", "developer", "scientist", "analyst", "designer", "manager",
    "intern", "architect", "administrator", "consultant", "specialist",
    "researcher", "programmer", "tester", "lead",
)

# Cities RADAR's users actually apply to, plus the generic remote marker.
_CITIES = (
    "Bangalore", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Delhi", "New Delhi",
    "Gurgaon", "Gurugram", "Noida", "Chennai", "Kolkata", "Ahmedabad", "Jaipur",
    "Indore", "Chandigarh", "Kochi", "Coimbatore", "Bhopal", "Lucknow",
    "London", "Berlin", "Dublin", "Toronto", "Singapore", "Sydney",
    "New York", "San Francisco", "Seattle", "Austin", "Boston", "Remote",
)


def _clean(value: str) -> str:
    return " ".join(value.split()).strip(" .,-–—|")


# Postings often run several fields together on one line ("Location: Pune.
# Duration: 6 months. Stipend: ..."), so a labelled value has to stop at the
# next label or sentence end rather than running to the end of the line.
_NEXT_FIELD_RE = re.compile(
    r"\.\s|\s{2,}|\b(?:duration|stipend|salary|compensation|ctc|type|apply|"
    r"eligibility|start date|deadline|experience|openings|posted)\b\s*[:\-]",
    re.I,
)


def _stop_at_next_field(value: str) -> str:
    return _NEXT_FIELD_RE.split(value, maxsplit=1)[0]


def guess_title(text: str, html: str = "") -> str:
    """Prefer the page <title>, else the first line that reads like a role."""
    if html:
        match = _TITLE_RE.search(html)
        if match:
            head = _clean(_TAG_RE.sub("", match.group(1)))
            # "Backend Intern - Acme | LinkedIn" -> "Backend Intern"
            head = re.split(_TITLE_SPLIT_RE, head)[0]
            if 2 <= len(head.split()) <= 10:
                return head
    for line in text.split("\n")[:40]:
        clean = _clean(_TITLE_SPLIT_RE.split(_clean(line))[0])
        if 2 <= len(clean.split()) <= 10 and any(w in clean.lower() for w in _ROLE_WORDS):
            return clean
    return ""


def guess_company(text: str, html: str = "", url: str = "") -> str:
    """Look for an explicit 'at X' / 'Company: X', else fall back to the domain."""
    for pattern in (
        r"(?:company|organisation|organization|employer)\s*[:\-]\s*([^\n|]{2,50})",
        r"\bat\s+([A-Z][\w&.\- ]{2,40}?)(?:\s*[|\n·]|\s+is\s|\s+we\s)",
    ):
        match = re.search(pattern, text, re.I)
        if match:
            name = _clean(_stop_at_next_field(match.group(1)))
            if name and len(name.split()) <= 5:
                return name
    if html:
        match = _TITLE_RE.search(html)
        if match:
            head = _clean(_TAG_RE.sub("", match.group(1)))
            parts = re.split(_TITLE_SPLIT_RE, head)
            if len(parts) > 1 and 0 < len(parts[1].split()) <= 5:
                return _clean(parts[1])
    if url:
        host = urllib.parse.urlparse(url).hostname or ""
        host = re.sub(r"^(www|jobs|careers|apply)\.", "", host)
        label = host.split(".")[0]
        # Generic boards say nothing about who the employer is.
        if label and label not in ("linkedin", "indeed", "internshala", "naukri",
                                   "glassdoor", "wellfound", "angel", "monster"):
            return label.replace("-", " ").title()
    return ""


def guess_stipend(text: str) -> str:
    if _UNPAID_RE.search(text):
        return "Unpaid"
    # Anchor on an explicit pay label first; a bare currency match anywhere on
    # the page is usually a price, not the salary.
    labelled = re.search(
        r"(?:stipend|salary|compensation|ctc|pay|package)\s*[:\-]?\s*(.{0,60})", text, re.I
    )
    if labelled:
        match = _STIPEND_RE.search(labelled.group(1))
        if match and any(c.isdigit() for c in match.group(0)):
            return _clean(match.group(0))
    match = _STIPEND_RE.search(text)
    if match and any(c.isdigit() for c in match.group(0)):
        return _clean(match.group(0))
    return ""


def guess_duration(text: str) -> str:
    labelled = re.search(r"(?:duration|period|length)\s*[:\-]?\s*(.{0,40})", text, re.I)
    for haystack in ([labelled.group(1)] if labelled else []) + [text]:
        match = _DURATION_RE.search(haystack)
        if match:
            return _clean(match.group(0))
    return ""


def guess_location(text: str) -> str:
    labelled = re.search(r"(?:location|based in|office)\s*[:\-]\s*([^\n|]{2,40})", text, re.I)
    if labelled:
        return _clean(_stop_at_next_field(labelled.group(1)))
    for city in _CITIES:
        if re.search(rf"\b{re.escape(city)}\b", text, re.I):
            return city
    return ""


def guess_work_mode(text: str) -> str:
    for mode, pattern in _MODE_PATTERNS:
        if pattern.search(text):
            return mode
    return ""


def guess_job_type(text: str) -> str:
    for job_type, pattern in _TYPE_PATTERNS:
        if pattern.search(text):
            return job_type
    return ""


def extract_meta(text: str, html: str = "", url: str = "") -> dict:
    """Pull every tracked field out of a posting. Missing values come back ''."""
    # The first part of a posting holds the summary block; searching it first
    # avoids picking up unrelated numbers from the page footer.
    head = "\n".join(text.split("\n")[:60])
    return {
        "title": guess_title(text, html),
        "company": guess_company(text, html, url),
        "job_type": guess_job_type(head) or guess_job_type(text),
        "work_mode": guess_work_mode(head) or guess_work_mode(text),
        "location": guess_location(head) or guess_location(text),
        "stipend": guess_stipend(head) or guess_stipend(text),
        "duration": guess_duration(head) or guess_duration(text),
    }


def ingest(url: str = "", text: str = "") -> dict:
    """
    Turn a link or pasted text into a parsed posting.

    Returns {source, url, jd_text, meta}. Raises FetchError when a link was
    given but could not be read, so the caller can prompt for pasted text.
    """
    if text.strip():
        body = html_to_text(text) if "<" in text and ">" in text else text.strip()
        return {
            "source": "pasted",
            "url": url.strip(),
            "jd_text": body,
            "meta": extract_meta(body, url=url),
        }
    if not url.strip():
        raise FetchError("Provide a job link or paste the description.")

    body, html = fetch(url)
    return {
        "source": "link",
        "url": url.strip(),
        "jd_text": body,
        "meta": extract_meta(body, html=html, url=url),
    }
