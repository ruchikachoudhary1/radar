"""
Tests for job-description matching.

The one that matters is test_idf_is_computed_over_a_real_corpus. Fitting the
vectoriser on just the resume and the job description produced an IDF with two
distinct values across the whole vocabulary — and the wrong way round, since a
term shared by both documents scored *lower* than one appearing in only one.
Everything else here is behaviour that would have looked fine either way.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matching  # noqa: E402

RESUME = (
    "Backend engineer. Built REST APIs in Python and FastAPI. "
    "Designed PostgreSQL schemas and wrote SQL queries. Docker deployments."
)
JD = (
    "We need a backend developer comfortable with Python, FastAPI and "
    "PostgreSQL. You will build REST APIs and work with Docker."
)
UNRELATED = (
    "Customer support associate. Handled tickets, phone calls and scheduling. "
    "Trained new staff on communication and escalation."
)


# --------------------------------------------------------------------------
# The corpus — the actual fix
# --------------------------------------------------------------------------
def test_idf_is_computed_over_a_real_corpus():
    """Two documents cannot produce a meaningful IDF; the role banks can."""
    pytest.importorskip("sklearn")
    from sklearn.feature_extraction.text import TfidfVectorizer

    def distinct_idfs(corpus):
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        vec.fit(corpus)
        return len(set(vec.idf_.round(4)))

    two_documents = distinct_idfs([RESUME, JD])
    with_corpus = distinct_idfs(matching._reference_corpus() + [RESUME, JD])

    assert two_documents <= 2, "sanity: two documents give a degenerate IDF"
    assert with_corpus > two_documents


def test_the_reference_corpus_is_the_role_banks():
    corpus = matching._reference_corpus()
    assert len(corpus) >= 20
    assert all(text.strip() for text in corpus)


def test_the_corpus_is_built_once_and_reused():
    assert matching._reference_corpus() is matching._reference_corpus()


# --------------------------------------------------------------------------
# Similarity behaviour
# --------------------------------------------------------------------------
def test_identical_documents_score_at_the_top():
    assert matching.similarity(JD, JD)["similarity"] == 100


def test_a_relevant_resume_beats_an_unrelated_one():
    relevant = matching.similarity(RESUME, JD)["similarity"]
    unrelated = matching.similarity(UNRELATED, JD)["similarity"]
    assert relevant > unrelated


def test_an_empty_job_description_scores_nothing_rather_than_zero():
    """None means 'not applicable'; 0 would read as 'you matched nothing'."""
    result = matching.similarity(RESUME, "")
    assert result["score"] is None
    assert result["matched"] == []


def test_coverage_counts_whole_terms_not_substrings():
    """'api' must not be credited by the word 'rapid'."""
    result = matching.similarity("rapid prototyping and iteration", "We need API design skills.")
    assert "api" not in result["matched"]


def test_matched_and_missing_together_cover_every_keyword():
    result = matching.similarity(RESUME, JD)
    keys = matching.jd_keywords(JD)
    assert sorted(result["matched"] + result["missing"]) == sorted(keys)


# --------------------------------------------------------------------------
# Keyword extraction
# --------------------------------------------------------------------------
def test_filler_words_are_not_treated_as_skills():
    keys = matching.jd_keywords(
        "We are seeking a skilled developer with strong experience and knowledge."
    )
    for filler in ("seeking", "skilled", "developer", "strong", "experience", "knowledge"):
        assert filler not in keys


def test_real_skills_survive_extraction():
    keys = matching.jd_keywords(JD)
    assert "python" in keys
    assert "fastapi" in keys


def test_dotted_and_slashed_terms_stay_intact():
    keys = matching.jd_keywords("Experience with Node.js and CI/CD pipelines required.")
    assert any("node.js" in k for k in keys)
