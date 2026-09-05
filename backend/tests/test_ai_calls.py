"""
Tests for the single place that talks to Gemini.

The point being protected: every outbound call in this project sets a timeout,
and the model calls — the slowest and most likely to hang — did not. A stalled
upstream held a worker open indefinitely, which on a free tier with very few
workers is enough to take the app down while the API key is technically fine.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ai  # noqa: E402
import coverletter  # noqa: E402
import interview  # noqa: E402
import tailor  # noqa: E402


class FakeModel:
    """Stands in for genai.GenerativeModel, recording how it was called."""

    def __init__(self, text="", raises=None):
        self.text, self.raises = text, raises
        self.calls = []

    def generate_content(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        if self.raises:
            raise self.raises
        return types.SimpleNamespace(text=self.text)


@pytest.fixture()
def fake_genai(monkeypatch):
    """Install a fake google.generativeai and pretend a key is configured."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    model = FakeModel()

    module = types.SimpleNamespace(
        configure=lambda **kw: None,
        GenerativeModel=lambda *a, **kw: model,
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", module)
    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(generativeai=module))
    return model


# --------------------------------------------------------------------------
# The timeout — the actual fix
# --------------------------------------------------------------------------
def test_every_model_call_carries_a_timeout(fake_genai):
    fake_genai.text = "a result"
    ai.generate("any prompt")

    assert len(fake_genai.calls) == 1
    options = fake_genai.calls[0]["kwargs"].get("request_options")
    assert options, "no request_options passed — a hung call would hang the request"
    assert options["timeout"] == ai.GEMINI_TIMEOUT_SECONDS
    assert 0 < ai.GEMINI_TIMEOUT_SECONDS <= 60


def test_a_timeout_reads_as_no_answer_rather_than_an_error(fake_genai):
    fake_genai.raises = TimeoutError("upstream stalled")
    assert ai.generate("any prompt") == ""


@pytest.mark.parametrize("failure", [
    TimeoutError("stalled"),
    ConnectionError("network down"),
    ValueError("quota exhausted"),
    RuntimeError("safety filter"),
])
def test_every_failure_mode_collapses_to_the_same_empty_answer(fake_genai, failure):
    """Callers branch on empty, so no failure needs handling twice."""
    fake_genai.raises = failure
    assert ai.generate("prompt") == ""


def test_no_key_means_no_call_at_all(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ai.generate("prompt") == ""


def test_a_response_with_no_text_is_treated_as_a_failure(fake_genai):
    fake_genai.text = None
    assert ai.generate("prompt") == ""


# --------------------------------------------------------------------------
# Every feature falls back rather than failing
# --------------------------------------------------------------------------
PROFILE = {
    "name": "Test Person",
    "skills": ["Python", "FastAPI"],
    "experience": "Built an API",
    "summary": "Backend focused",
}
JD = "Backend role needing Python and FastAPI."


def test_bullet_rewrite_falls_back_when_the_model_times_out(fake_genai):
    fake_genai.raises = TimeoutError("stalled")
    result = ai.rewrite_bullet("worked on the backend")
    assert result["engine"] == "rule-based"
    assert result["variants"]


def test_tailoring_falls_back_when_the_model_times_out(fake_genai):
    fake_genai.raises = TimeoutError("stalled")
    result = tailor.tailor(PROFILE, JD, {"title": "Backend Dev", "company": "Acme"})
    assert result["engine"] == "rule-based"
    assert result["resume_text"].strip()


def test_cover_letters_fall_back_when_the_model_times_out(fake_genai):
    fake_genai.raises = TimeoutError("stalled")
    result = coverletter.write(PROFILE, JD, {"title": "Backend Dev", "company": "Acme"})
    assert result["engine"] == "rule-based"
    assert result["letter_text"].strip()


def test_question_polish_falls_back_when_the_model_returns_prose(fake_genai):
    """A model answering in sentences instead of JSON must not raise."""
    fake_genai.text = "Sure! Here are some nicer questions for you."
    questions = [{"id": "q1", "question": "What was the metric?", "area": "Impact"}]
    assert interview._gemini_polish(questions, "backend") == []


def test_question_polish_uses_the_model_when_it_returns_valid_json(fake_genai):
    fake_genai.text = '[{"id": "q1", "question": "Reworded nicely?"}]'
    questions = [{"id": "q1", "question": "Original?", "area": "Impact"}]
    out = interview._gemini_polish(questions, "backend")
    assert out[0]["question"] == "Reworded nicely?"
    assert out[0]["area"] == "Impact", "unrelated fields must survive the merge"
