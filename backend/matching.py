"""
Job-description matching.

Uses TF-IDF vectorisation + cosine similarity to score how closely a resume
aligns with a pasted job description, and to surface the JD's most important
terms that are missing from the resume. TF-IDF is fast, dependency-light and
fully explainable — every number traces back to term frequency.

A note on the corpus, because this is the part that is easy to get wrong.

IDF only means anything when it is computed over a body of documents. Fitting
the vectoriser on just the resume and the job description — two documents —
gives an IDF that is not merely useless but backwards: a term appearing in both
documents gets a *lower* weight than one appearing in a single document, which
is the opposite of what similarity scoring wants. The vectoriser is therefore
fitted over the 21 curated role skill banks as well as the two documents being
compared, so a term's weight reflects how common it is across the domain rather
than across a sample of two.

That is still a small corpus. A production system would derive IDF from many
thousands of real resumes and postings; these 21 banks are a reasonable
stand-in for a project of this size, and the limitation is stated rather than
hidden.
"""
from __future__ import annotations

import re

from roles import ROLE_KEYWORDS

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "this", "that", "from", "was", "were", "has", "had", "not", "but", "all",
    "who", "can", "job", "role", "team", "work", "working", "years", "year",
    "experience", "including", "etc", "such", "using", "use", "used", "able",
    "strong", "good", "plus", "well", "must", "should", "would", "into", "per",
    "a", "an", "of", "to", "in", "on", "at", "as", "is", "be", "or", "we", "it",
    # Generic job-description filler that is not an actual skill/keyword.
    "seek", "seeking", "skilled", "developer", "engineer", "required", "require",
    "requirements", "requirement", "preferred", "prefer", "ability", "knowledge",
    "understanding", "familiarity", "candidate", "candidates", "looking", "join",
    "help", "ideal", "responsibilities", "qualifications", "degree", "related",
    "field", "environment", "excellent", "solid", "proven", "hands", "based",
    "min", "years'", "including", "across", "within", "their", "them", "they",
}

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.#/-]{1,}")

# Characters that count as "part of a keyword". A keyword only counts as
# mentioned when it is not touching one of these on either side.
#
# This exists because a plain substring test silently inflates every score:
# "go" appears inside "algorithms", "ai" inside "maintained", "api" inside
# "rapid". A plain \b does not work either, because entries like "c++",
# "node.js" and "ci/cd" end in punctuation, and \b after "+" asserts the
# opposite of what is wanted. Expressing the boundary as "not adjacent to
# another keyword character" handles both cases.
_KEYWORD_CHARS = r"a-z0-9+#./\-"
_MENTION_CACHE: dict[str, re.Pattern] = {}


def mentions(keyword: str, low_text: str) -> bool:
    """Is `keyword` present in already-lowercased `low_text` as a whole term?"""
    keyword = keyword.strip().lower()
    if not keyword:
        return False
    pattern = _MENTION_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(
            rf"(?<![{_KEYWORD_CHARS}]){re.escape(keyword)}(?![{_KEYWORD_CHARS}])"
        )
        _MENTION_CACHE[keyword] = pattern
    return pattern.search(low_text) is not None


def _tokens(text: str) -> list[str]:
    out = []
    for raw in TOKEN_RE.findall(text.lower()):
        # Trim trailing/leading punctuation ("aws." -> "aws") but keep internal
        # separators intact ("node.js", "ci/cd").
        t = raw.strip(".-/")
        if len(t) > 2 and t not in STOPWORDS:
            out.append(t)
    return out


def jd_keywords(jd_text: str, top_n: int = 25) -> list[str]:
    """Return the most salient keywords from a job description."""
    from collections import Counter

    counts = Counter(_tokens(jd_text))
    return [word for word, _ in counts.most_common(top_n)]


def warm_up() -> None:
    """
    Import scikit-learn and build the corpus before any user asks for them.

    The sklearn imports below are inside similarity() so that a missing or
    broken install degrades to keyword overlap instead of crashing the app.
    The cost of that is paid by whoever makes the first request: importing
    scikit-learn takes several seconds, and on a free tier that sleeps after
    fifteen minutes it is paid again after every wake-up.

    Called at startup so the process absorbs it instead of a person waiting on
    an upload. Failure is deliberately silent — this is an optimisation, and
    similarity() still has its own fallback.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1).fit(
            _reference_corpus()
        )
    except Exception:
        pass


def _reference_corpus() -> list[str]:
    """
    The 21 role skill banks as documents, used to give IDF a real corpus.

    Built once and reused: the banks do not change at runtime, and rebuilding
    the list on every request would be pure waste.
    """
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = [" ".join(bank) for bank in ROLE_KEYWORDS.values() if bank]
    return _CORPUS


_CORPUS: list[str] | None = None


def similarity(resume_text: str, jd_text: str) -> dict:
    """Cosine similarity between resume and JD, plus matched/missing terms."""
    if not jd_text.strip():
        return {"score": None, "matched": [], "missing": []}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        # The two documents under comparison go last, so their rows are the
        # final two after fitting; everything before them is the reference
        # corpus that gives IDF something to measure against.
        corpus = _reference_corpus() + [resume_text, jd_text]
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform(corpus)
        cos = float(cosine_similarity(matrix[-2], matrix[-1])[0][0])
    except Exception:
        # Pure-python Jaccard fallback if scikit-learn is unavailable.
        r, j = set(_tokens(resume_text)), set(_tokens(jd_text))
        cos = len(r & j) / len(r | j) if (r | j) else 0.0

    keys = jd_keywords(jd_text)
    low_resume = resume_text.lower()
    matched = [k for k in keys if mentions(k, low_resume)]
    missing = [k for k in keys if not mentions(k, low_resume)]
    coverage = round(100 * len(matched) / len(keys)) if keys else None

    return {
        "score": coverage,          # headline: % of JD keywords covered
        "similarity": round(cos * 100),  # secondary: TF-IDF cosine similarity
        "matched": matched,
        "missing": missing,
    }
