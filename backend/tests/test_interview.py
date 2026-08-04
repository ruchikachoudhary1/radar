"""
Unit tests for the gap-fill interview and document export.

These run entirely offline — no GEMINI_API_KEY is needed, which is the point:
the rule layer must stand on its own.

Run with pytest:      pytest
Or standalone:        python tests/test_interview.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import documents
import interview
import scoring

GAPPY_RESUME = """
Yug Sharma

EXPERIENCE
Was responsible for the college fest website and its content updates.
Worked on a chatbot with the robotics club during the summer.

PROJECTS
Helped build an attendance tracker for the department.
"""


def _report(text, role="Backend Developer"):
    return scoring.grade(text, role=role)


def test_finds_missing_contact_details():
    qs = interview.find_gaps(GAPPY_RESUME, _report(GAPPY_RESUME), "Backend Developer")
    ids = {q["id"] for q in qs}
    # No email, phone, LinkedIn or GitHub anywhere in the text.
    assert "contact_email" in ids
    assert "contact_phone" in ids


def test_asks_for_metrics_on_unquantified_bullets():
    qs = interview.find_gaps(GAPPY_RESUME, _report(GAPPY_RESUME), "Backend Developer")
    metric_qs = [q for q in qs if q["id"].startswith("metric_")]
    assert metric_qs, "expected at least one 'add a number' question"
    # Each metric question must carry the bullet it refers to, so the rebuild
    # step knows which line to patch.
    assert all(q["context"] for q in metric_qs)


def test_question_count_is_capped():
    qs = interview.find_gaps(GAPPY_RESUME, _report(GAPPY_RESUME), "Backend Developer")
    assert 0 < len(qs) <= interview.MAX_QUESTIONS


def test_every_question_has_a_unique_id():
    qs = interview.find_gaps(GAPPY_RESUME, _report(GAPPY_RESUME), "Backend Developer")
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids))


def test_no_answers_returns_resume_unchanged():
    qs = interview.find_gaps(GAPPY_RESUME, _report(GAPPY_RESUME))
    out = interview.rebuild(GAPPY_RESUME, qs, {})
    assert out["engine"] == "none"
    assert out["resume_text"] == GAPPY_RESUME


def test_rule_rebuild_injects_contact_and_metrics():
    report = _report(GAPPY_RESUME)
    qs = interview.find_gaps(GAPPY_RESUME, report, "Backend Developer")
    answers = {}
    for q in qs:
        if q["id"] == "contact_email":
            answers[q["id"]] = "yug@example.com"
        elif q["id"].startswith("metric_"):
            answers[q["id"]] = "cutting load time by 40%"

    out = interview.rebuild(GAPPY_RESUME, qs, answers)
    text = out["resume_text"]
    assert "yug@example.com" in text
    if any(k.startswith("metric_") for k in answers):
        assert "40%" in text
    assert out["changes"], "rebuild should report what it changed"


def test_rebuild_raises_the_score():
    report = _report(GAPPY_RESUME)
    qs = interview.find_gaps(GAPPY_RESUME, report, "Backend Developer")
    answers = {
        q["id"]: (
            "yug@example.com" if q["id"] == "contact_email"
            else "+91 98765 43210" if q["id"] == "contact_phone"
            else "linkedin.com/in/yug" if q["id"] == "contact_linkedin"
            else "github.com/yug" if q["id"] == "contact_github"
            else "serving 500 students, cutting manual work by 60%"
        )
        for q in qs
    }
    out = interview.rebuild(GAPPY_RESUME, qs, answers)
    after = scoring.grade(out["resume_text"], role="Backend Developer")
    assert after["overall"] > report["overall"]


def test_parse_blocks_classifies_structure():
    blocks = documents.parse_blocks("Yug Sharma\n\nEXPERIENCE\n- Built a thing\nPlain line")
    kinds = [k for k, _ in blocks if k != "blank"]
    assert kinds == ["name", "heading", "bullet", "body"]


def test_docx_export_produces_a_zip():
    data = documents.to_docx("Yug Sharma\n\nEXPERIENCE\n- Built a thing that scaled to 500 users")
    assert data[:2] == b"PK", "a .docx is a zip archive"


def test_pdf_export_produces_a_pdf():
    data = documents.to_pdf("Yug Sharma\n\nEXPERIENCE\n- Built a thing — with an em dash")
    assert data[:4] == b"%PDF"


def test_safe_filename_strips_junk():
    assert documents.safe_filename("my resume (final).pdf", "docx") == "my_resume_final.docx"


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
