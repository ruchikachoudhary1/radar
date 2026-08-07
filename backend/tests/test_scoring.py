"""
Unit tests for the RADAR analysis engine.

Run with pytest:      pytest
Or standalone:        python tests/test_scoring.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ai
import matching
import parsing
import scoring

STRONG_RESUME = """
EXPERIENCE
Software Engineer
Built a React dashboard that reduced reporting time by 40% for 200 users.
Optimized SQL queries, improving load time by 55%.
Led a team of 4 to ship a payments service handling 10000 requests per day.

PROJECTS
Engineered a full-stack tracker with JWT auth serving 500 users.
"""

WEAK_RESUME = """
EXPERIENCE
Intern
Worked on some tasks for the team.
Responsible for the website and other duties.
Helped with testing when needed.
"""


def test_weights_sum_to_100():
    assert sum(scoring.WEIGHTS.values()) == 100


def test_strong_resume_beats_weak():
    strong = scoring.grade(STRONG_RESUME, role="Full Stack Developer")
    weak = scoring.grade(WEAK_RESUME, role="Full Stack Developer")
    assert strong["overall"] > weak["overall"]


def test_grade_letters_are_ordered():
    strong = scoring.grade(STRONG_RESUME, role="Full Stack Developer")
    assert strong["grade"] in {"A", "B", "C", "D"}
    assert 0 <= strong["overall"] <= 100


def test_sections_detected():
    result = scoring.score_sections("EDUCATION\nEXPERIENCE\nSKILLS\nPROJECTS\nemail@x.com")
    assert "education" in result["found"]
    assert result["points"] > 0


def test_impact_rewards_numbers():
    with_numbers = scoring.score_impact(STRONG_RESUME)
    without = scoring.score_impact(WEAK_RESUME)
    assert with_numbers["points"] >= without["points"]


def test_action_language_penalises_weak_openers():
    weak = scoring.score_action_language(WEAK_RESUME)
    strong = scoring.score_action_language(STRONG_RESUME)
    assert strong["points"] > weak["points"]


def test_contact_detection():
    r = scoring.score_contact("Reach me at a@b.com or +91 98765 43210, github.com/x, linkedin.com/in/x")
    assert r["points"] == r["max"]


def test_bullet_parsing_is_section_aware():
    bullets = parsing.split_bullets(STRONG_RESUME)
    # Role title "Software Engineer" (2 words) and headers are excluded.
    assert all("dashboard" in b or "SQL" in b or "team" in b or "tracker" in b for b in bullets)
    assert len(bullets) >= 3


def test_jd_keywords_are_clean():
    kws = matching.jd_keywords("We need React, FastAPI and AWS. Testing required.")
    assert "aws" in kws          # trailing period stripped
    assert "required" not in kws  # filler word removed
    assert all(not k.endswith(".") for k in kws)


def test_jd_similarity_returns_coverage():
    res = matching.similarity("React FastAPI AWS Docker", "Need React and FastAPI and AWS")
    assert 0 <= res["score"] <= 100
    assert "react" in res["matched"]


def test_rewrite_fallback_always_returns_variants():
    out = ai.rewrite_bullet("Worked on the login page")
    assert out["variants"]
    # Weak opener stripped, leads with the real action.
    assert not out["variants"][0].lower().startswith("worked on")


def test_empty_bullet_is_safe():
    assert ai.rewrite_bullet("")["variants"] == []


def _run_standalone():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa
            print(f"  ERROR {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_standalone() else 1)


# --------------------------------------------------------------------------
# Keyword matching must be whole-term, not substring
#
# The original `kw in text` handed points to resumes that never mentioned the
# skill: "go" sits inside "algorithms", "ai" inside "maintained", "api" inside
# "rapid". Role match is 25 of the 100 points, so this inflated every score.
# --------------------------------------------------------------------------
from matching import mentions  # noqa: E402


@pytest.mark.parametrize("keyword,text", [
    ("go", "improved algorithms and logistics"),
    ("ai", "maintained and explained the process"),
    ("api", "rapid prototyping"),
    ("sql", "PostgreSQL experience"),
    ("r", "customer support"),
    ("go", "go-to-market strategy"),
])
def test_a_keyword_hidden_inside_another_word_does_not_count(keyword, text):
    assert not mentions(keyword, text.lower())


@pytest.mark.parametrize("keyword,text", [
    ("go", "built services in Go and Python"),
    ("ai", "AI and machine learning"),
    ("api", "designed a REST API"),
    ("sql", "wrote SQL queries"),
    ("react", "React and Redux"),
])
def test_a_keyword_used_as_a_word_does_count(keyword, text):
    assert mentions(keyword, text.lower())


@pytest.mark.parametrize("keyword,text", [
    ("c++", "wrote C++ and Python"),
    ("c#", "C# and .NET"),
    ("node.js", "Node.js and Express"),
    ("ci/cd", "CI/CD pipelines"),
    ("scikit-learn", "used scikit-learn for the model"),
    ("a/b testing", "ran A/B testing on the funnel"),
])
def test_keywords_ending_in_punctuation_still_match(keyword, text):
    """A plain \b breaks on these — \b after '+' asserts the opposite."""
    assert mentions(keyword, text.lower())


def test_an_unrelated_resume_scores_near_zero_on_role_match():
    """The regression this guards: a support CV scoring as a backend engineer."""
    resume = (
        "Customer support associate. Managed algorithms for scheduling. "
        "Excellent communication skills. Coordinated logistics and reporting. "
    ) * 4
    result = scoring.score_role_match(resume, "Backend Developer", None)
    assert result["points"] <= 2
    assert "go" not in result["matched"]


def test_matching_is_case_insensitive():
    assert mentions("python", "PYTHON and Django".lower())
    assert mentions("fastapi", "Built with FastAPI".lower())
