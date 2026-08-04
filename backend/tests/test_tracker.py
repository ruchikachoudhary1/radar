"""Tests for the master profile, job posting parsing and per-job tailoring."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jobs
import profiles
import tailor

RESUME = """Aditya Sharma
aditya.sharma@gmail.com · +91 98765 43210 · Bengaluru, India
linkedin.com/in/aditya-sharma · github.com/adityasharma

SUMMARY
Final-year computer science student targeting backend engineering roles.

TECHNICAL SKILLS
Languages: Python, JavaScript, SQL
Web: React, FastAPI, Node
Tools: Docker, Git, PostgreSQL

EXPERIENCE
Software Engineering Intern — Techlabs (Jun 2024 – Dec 2024)
Built a React dashboard that cut reporting time by 40% for 200+ users.

PROJECTS
Smart Expense Tracker — React, FastAPI, PostgreSQL
Engineered a full-stack tracker with JWT auth serving 500 users.

EDUCATION
Parul University — B.Tech, Computer Science Engineering (2021–2025)
"""

POSTING_HTML = """<html><head><title>Backend Developer Intern - Acme Labs | Careers</title></head>
<body><script>var tracking = 1;</script>
<h1>Backend Developer Intern</h1>
<p>Location: Bengaluru</p>
<p>This is a 6 months internship and the role is fully remote.</p>
<p>Stipend: Rs. 25,000 /month</p>
<p>We want strong Python, FastAPI, PostgreSQL and Docker skills. You will design
REST APIs, work on microservices, and help maintain our CI/CD pipelines.</p>
</body></html>"""


# --------------------------------------------------------------------------
# Profile extraction
# --------------------------------------------------------------------------
def test_extract_pulls_contact_details():
    p = profiles.extract(RESUME)
    assert p["name"] == "Aditya Sharma"
    assert p["email"] == "aditya.sharma@gmail.com"
    assert "linkedin.com/in/aditya-sharma" in p["linkedin"]
    assert "github.com/adityasharma" in p["github"]


def test_extract_flattens_labelled_skill_groups():
    skills = [s.lower() for s in profiles.extract(RESUME)["skills"]]
    assert "python" in skills
    assert "fastapi" in skills
    # "Languages:" is a group label, not a skill.
    assert not any(s.startswith("languages") for s in skills)


def test_extract_finds_sections_under_aliased_headings():
    p = profiles.extract(RESUME)
    assert "Techlabs" in p["experience"]
    assert "Expense Tracker" in p["projects"]
    assert "Parul University" in p["education"]


def test_render_round_trips_through_extract():
    once = profiles.extract(RESUME)
    twice = profiles.extract(profiles.render(once))
    assert twice["name"] == once["name"]
    assert twice["email"] == once["email"]
    assert set(s.lower() for s in twice["skills"]) >= {"python", "fastapi"}


def test_normalise_accepts_comma_separated_skills_and_drops_extras():
    clean = profiles.normalise({"name": " Ada ", "skills": "Python, , Go ", "nope": "x"})
    assert clean["name"] == "Ada"
    assert clean["skills"] == ["Python", "Go"]
    assert "nope" not in clean


def test_is_usable_requires_name_and_substance():
    assert not profiles.is_usable(profiles.empty())
    assert not profiles.is_usable({"name": "Ada", "skills": []})
    assert profiles.is_usable({"name": "Ada", "skills": ["Python"]})


# --------------------------------------------------------------------------
# Job posting parsing
# --------------------------------------------------------------------------
def test_html_to_text_drops_scripts_and_tags():
    text = jobs.html_to_text(POSTING_HTML)
    assert "tracking" not in text
    assert "<p>" not in text
    assert "Backend Developer Intern" in text


def test_extract_meta_reads_every_tracked_field():
    text = jobs.html_to_text(POSTING_HTML)
    meta = jobs.extract_meta(text, html=POSTING_HTML, url="https://acmelabs.com/jobs/1")
    assert meta["title"] == "Backend Developer Intern"
    assert meta["company"] == "Acme Labs"
    assert meta["job_type"] == "Internship"
    assert meta["work_mode"] == "Remote"
    assert meta["location"] == "Bengaluru"
    assert "25,000" in meta["stipend"]
    assert meta["duration"] == "6 months"


def test_unpaid_postings_are_labelled_not_left_blank():
    assert jobs.guess_stipend("This is an unpaid internship for 3 months.") == "Unpaid"


def test_stipend_prefers_a_labelled_figure_over_a_stray_number():
    text = "Apply to 500 openings. Stipend: Rs. 20,000 /month"
    assert "20,000" in jobs.guess_stipend(text)


def test_labelled_fields_do_not_swallow_the_ones_after_them():
    text = "Location: Bengaluru. Duration: 6 months. Stipend: Rs. 25,000 /month"
    meta = jobs.extract_meta(text)
    assert meta["location"] == "Bengaluru"
    assert meta["duration"] == "6 months"
    assert "25,000" in meta["stipend"]


def test_title_from_plain_text_drops_the_company_suffix():
    assert jobs.guess_title("Backend Developer Intern at Acme Labs\nApply now.") == (
        "Backend Developer Intern"
    )


def test_missing_fields_come_back_empty_rather_than_guessed():
    meta = jobs.extract_meta("We are hiring. Apply now. " * 20)
    assert meta["stipend"] == ""
    assert meta["duration"] == ""
    assert meta["work_mode"] == ""


def test_generic_job_boards_do_not_become_the_company_name():
    text = "Some posting body. " * 30
    assert jobs.guess_company(text, url="https://www.linkedin.com/jobs/view/1") == ""
    assert jobs.guess_company(text, url="https://careers.acmelabs.com/1") == "Acmelabs"


def test_ingest_uses_pasted_text_without_touching_the_network():
    res = jobs.ingest(text=POSTING_HTML)
    assert res["source"] == "pasted"
    assert res["meta"]["job_type"] == "Internship"


def test_ingest_without_url_or_text_is_rejected():
    with pytest.raises(jobs.FetchError):
        jobs.ingest()


# --------------------------------------------------------------------------
# SSRF guard — the fetch runs server-side on a user-supplied URL
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/api/health",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
    ],
)
def test_fetch_refuses_private_and_loopback_addresses(url):
    with pytest.raises(jobs.FetchError):
        jobs.fetch(url)


def test_fetch_refuses_non_http_schemes():
    with pytest.raises(jobs.FetchError):
        jobs.fetch("file:///etc/passwd")


# --------------------------------------------------------------------------
# Tailoring
# --------------------------------------------------------------------------
def test_tailoring_leads_with_the_skills_the_posting_asks_for():
    profile = profiles.extract(RESUME)
    jd = jobs.html_to_text(POSTING_HTML)
    result = tailor.tailor(profile, jd, {"title": "Backend Developer Intern"})

    lines = result["resume_text"].split("\n")
    skills_line = lines[lines.index("SKILLS") + 1]
    ranked = [s.strip().lower() for s in skills_line.split(",")]
    assert ranked.index("python") < ranked.index("react")


def test_tailoring_improves_keyword_coverage():
    profile = profiles.extract(RESUME)
    jd = jobs.html_to_text(POSTING_HTML)
    result = tailor.tailor(profile, jd, {"title": "Backend Developer Intern"})
    assert result["match"]["score"] >= result["baseline_match"]["score"]


def test_tailoring_never_invents_skills_the_profile_lacks():
    profile = profiles.extract(RESUME)
    jd = "We need Kubernetes, Rust and Terraform experience."
    text = tailor.tailor(profile, jd, {})["resume_text"].lower()
    assert "kubernetes" not in text
    assert "rust" not in text
    assert "terraform" not in text


def test_tailoring_works_with_no_job_description():
    profile = profiles.extract(RESUME)
    result = tailor.tailor(profile, "", {})
    assert "Aditya Sharma" in result["resume_text"]
    assert result["engine"] == "rule-based"
