"""
Tests for the cover letter writer.

These run against the rule engine — no API key in CI — which is the path that
has to hold up when Gemini is unavailable. The point being protected is that
the letter never states anything the profile did not.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import coverletter  # noqa: E402

PROFILE = {
    "name": "Aditya Sharma",
    "email": "aditya@example.com",
    "summary": "Final-year CS student focused on backend systems.",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React", "Figma"],
    "experience": "Built an internal reporting API at a campus startup\nMaintained a CI pipeline",
    "projects": "RADAR — resume analyser using scikit-learn",
    "education": "B.Tech Computer Science, 2026",
}

JD = """Backend Engineering Intern at Zomato. We need someone comfortable with Python,
FastAPI and PostgreSQL. You will build REST APIs and work with Docker."""

META = {"title": "Backend Engineering Intern", "company": "Zomato"}


def write(profile=None, jd=JD, meta=None):
    return coverletter.write(profile or PROFILE, jd, meta if meta is not None else META)


def test_the_letter_names_the_role_and_company():
    text = write()["letter_text"]
    assert "Backend Engineering Intern" in text
    assert "Zomato" in text


def test_it_leads_with_skills_the_posting_actually_asked_for():
    text = write()["letter_text"]
    for skill in ("Python", "FastAPI", "PostgreSQL"):
        assert skill in text


def test_it_does_not_claim_skills_the_posting_never_mentioned():
    """Figma is on the profile but irrelevant here — it should not be pitched."""
    assert "Figma" not in write()["letter_text"]


def test_it_never_invents_a_company_the_profile_does_not_contain():
    text = write()["letter_text"]
    for invented in ("Google", "Microsoft", "Amazon", "Infosys"):
        assert invented not in text


def test_it_signs_off_with_the_profile_name():
    assert write()["letter_text"].strip().endswith("Aditya Sharma")


def test_a_thin_profile_leaves_a_marked_placeholder_rather_than_inventing():
    thin = {"name": "Riya", "skills": [], "summary": "", "experience": "", "projects": ""}
    result = write(thin, jd="Some role requiring Rust and Kubernetes.", meta={})
    assert result["placeholders"] > 0
    assert "[add" in result["letter_text"]


def test_the_rule_engine_is_used_when_no_key_is_configured():
    assert write()["engine"] == "rule-based"


def test_it_works_with_no_job_description_at_all():
    """Saving a posting we could not read must not break letter writing."""
    result = write(jd="", meta=META)
    assert result["letter_text"].strip()
    assert "Backend Engineering Intern" in result["letter_text"]


def test_it_works_with_no_meta_at_all():
    result = write(meta={})
    assert result["letter_text"].strip()
    assert result["word_count"] > 20


def test_the_letter_stays_short_enough_to_read():
    assert write()["word_count"] < 320


@pytest.mark.parametrize("skills,expected", [
    (["Python"], "Python"),
    (["Python", "FastAPI"], "Python and FastAPI"),
    (["Python", "FastAPI", "Docker"], "Python, FastAPI and Docker"),
])
def test_skill_lists_read_as_english_not_as_arrays(skills, expected):
    assert coverletter._join(skills) == expected
