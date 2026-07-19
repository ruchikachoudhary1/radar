"""
Job-description matching.

Uses TF-IDF vectorisation + cosine similarity to score how closely a resume
aligns with a pasted job description, and to surface the JD's most important
terms that are missing from the resume. TF-IDF is fast, dependency-light and
fully explainable in a viva — every number can be traced back to term frequency.
"""
from __future__ import annotations

import re

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


def similarity(resume_text: str, jd_text: str) -> dict:
    """Cosine similarity between resume and JD, plus matched/missing terms."""
    if not jd_text.strip():
        return {"score": None, "matched": [], "missing": []}

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        matrix = vec.fit_transform([resume_text, jd_text])
        cos = float(cosine_similarity(matrix[0], matrix[1])[0][0])
    except Exception:
        # Pure-python Jaccard fallback if scikit-learn is unavailable.
        r, j = set(_tokens(resume_text)), set(_tokens(jd_text))
        cos = len(r & j) / len(r | j) if (r | j) else 0.0

    keys = jd_keywords(jd_text)
    low_resume = resume_text.lower()
    matched = [k for k in keys if k in low_resume]
    missing = [k for k in keys if k not in low_resume]
    coverage = round(100 * len(matched) / len(keys)) if keys else None

    return {
        "score": coverage,          # headline: % of JD keywords covered
        "similarity": round(cos * 100),  # secondary: TF-IDF cosine similarity
        "matched": matched,
        "missing": missing,
    }
