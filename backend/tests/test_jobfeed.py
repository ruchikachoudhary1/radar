"""
Tests for the job feed.

Network calls are stubbed. These tests are about the parts that break in
practice: a board name that could redirect the request somewhere it shouldn't
go, one dead board taking the whole feed down with it, and the filters being
strict enough to be useful without being so strict they show nothing.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jobfeed  # noqa: E402

GREENHOUSE_PAYLOAD = {
    "jobs": [
        {
            "id": 101,
            "title": "Backend Engineering Intern",
            "company_name": "Acme",
            "location": {"name": "Bengaluru, India"},
            "absolute_url": "https://acme.com/jobs/101",
            "first_published": "2026-08-01T10:00:00-04:00",
        },
        {
            "id": 102,
            "title": "Senior Product Manager",
            "company_name": "Acme",
            "location": {"name": "Remote - India"},
            "absolute_url": "https://acme.com/jobs/102",
            "first_published": "2026-07-20T10:00:00-04:00",
        },
        {
            # No URL — a placeholder row that should be dropped.
            "id": 103,
            "title": "Ghost Role",
            "company_name": "Acme",
            "location": {"name": "London"},
            "absolute_url": "",
        },
    ]
}

LEVER_PAYLOAD = [
    {
        "id": "abc-1",
        "text": "Machine Learning Intern",
        "categories": {"location": "Remote", "commitment": "Internship"},
        "hostedUrl": "https://jobs.lever.co/beta/abc-1",
        "createdAt": 1785000000000,
    }
]


@pytest.fixture()
def stub(monkeypatch):
    """Swap the HTTP layer for a lookup so no test touches the network."""
    responses = {}

    def fake_get(url):
        for fragment, payload in responses.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise jobfeed.FeedError("No public job board found for that name.")

    monkeypatch.setattr(jobfeed, "_get", fake_get)
    return responses


# --------------------------------------------------------------------------
# Board name handling — the part that could be abused
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    "../../etc/passwd",
    "acme/../../admin",
    "acme?x=1",
    "acme#frag",
    "http://evil.com/x",
    "acme com",
    "",
    "a" * 100,
])
def test_a_board_name_that_could_redirect_the_request_is_refused(bad):
    """The token goes into the URL path, so it cannot be free-form."""
    with pytest.raises(jobfeed.FeedError):
        jobfeed.fetch_board("greenhouse", bad)


def test_an_unknown_source_is_refused():
    with pytest.raises(jobfeed.FeedError):
        jobfeed.fetch_board("linkedin", "acme")


@pytest.mark.parametrize("good", ["acme", "acme-labs", "acme_labs", "acme.io", "Acme123"])
def test_ordinary_board_names_are_allowed(good, stub):
    stub["greenhouse"] = {"jobs": []}
    assert jobfeed.fetch_board("greenhouse", good) == []


# --------------------------------------------------------------------------
# Parsing each source into one shape
# --------------------------------------------------------------------------
def test_greenhouse_postings_are_normalised(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    jobs = jobfeed.fetch_board("greenhouse", "acme")

    assert len(jobs) == 2  # the one with no URL is dropped
    first = jobs[0]
    assert first["title"] == "Backend Engineering Intern"
    assert first["company"] == "Acme"
    assert first["location"] == "Bengaluru, India"
    assert first["url"] == "https://acme.com/jobs/101"
    assert first["posted_at"] == "2026-08-01"
    assert first["internship"] is True
    assert first["remote"] is False


def test_lever_postings_are_normalised_to_the_same_shape(stub):
    stub["lever"] = LEVER_PAYLOAD
    jobs = jobfeed.fetch_board("lever", "beta")

    assert jobs[0]["source"] == "lever"
    assert jobs[0]["title"] == "Machine Learning Intern"
    assert jobs[0]["remote"] is True
    assert jobs[0]["internship"] is True


NORMALISED_FIELDS = {
    "source", "external_id", "company", "title", "location", "url",
    "posted_at", "remote", "internship",
}


def test_both_sources_produce_identical_field_sets(stub):
    """The UI renders one card shape, so the adapters must agree exactly."""
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    stub["lever"] = LEVER_PAYLOAD

    gh = jobfeed.fetch_board("greenhouse", "acme")[0]
    lv = jobfeed.fetch_board("lever", "beta")[0]
    assert set(gh) == set(lv) == NORMALISED_FIELDS


def test_lever_reports_an_unknown_board_with_a_200_and_ok_false(stub):
    """Lever does not 404 for a bad board, so the body has to be checked."""
    stub["lever"] = {"ok": False, "error": "Document not found"}
    with pytest.raises(jobfeed.FeedError):
        jobfeed.fetch_board("lever", "nosuchcompany")


def test_remote_is_detected_from_the_location_text(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    pm = [j for j in jobfeed.fetch_board("greenhouse", "acme") if "Product" in j["title"]][0]
    assert pm["remote"] is True


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------
JOB = {"title": "Backend Engineering Intern", "location": "Bengaluru, India",
       "remote": False, "internship": True}


def test_no_preferences_means_everything_matches():
    """An empty feed reads as broken; 'you haven't chosen yet' is not an error."""
    assert jobfeed.matches(JOB, {})
    assert jobfeed.matches(JOB, {"roles": [], "locations": []})


def test_role_keywords_filter_on_the_title():
    assert jobfeed.matches(JOB, {"roles": ["backend"]})
    assert jobfeed.matches(JOB, {"roles": ["frontend", "backend"]})
    assert not jobfeed.matches(JOB, {"roles": ["designer"]})


def test_internships_only_excludes_full_time_roles():
    full_time = {**JOB, "title": "Backend Engineer", "internship": False}
    assert not jobfeed.matches(full_time, {"internships_only": True})
    assert jobfeed.matches(JOB, {"internships_only": True})


def test_remote_only_excludes_office_roles():
    assert not jobfeed.matches(JOB, {"remote_only": True})
    assert jobfeed.matches({**JOB, "remote": True}, {"remote_only": True})


def test_location_filter_applies_to_office_roles():
    assert jobfeed.matches(JOB, {"locations": ["Bengaluru"]})
    assert not jobfeed.matches(JOB, {"locations": ["Delhi"]})


def test_a_remote_role_passes_the_location_filter_wherever_you_live():
    """Remote means location is irrelevant, not that it failed to match."""
    remote = {**JOB, "remote": True, "location": "Remote"}
    assert jobfeed.matches(remote, {"locations": ["Delhi"]})


# --------------------------------------------------------------------------
# Collecting across boards
# --------------------------------------------------------------------------
def test_one_dead_board_does_not_empty_the_whole_feed(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    stub["lever"] = jobfeed.FeedError("Couldn't reach that board. It may be down.")

    result = jobfeed.collect([
        {"source": "greenhouse", "token": "acme"},
        {"source": "lever", "token": "beta"},
    ])

    assert len(result["jobs"]) == 2
    assert len(result["problems"]) == 1
    assert result["problems"][0]["token"] == "beta"


def test_results_are_sorted_newest_first(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    jobs = jobfeed.collect([{"source": "greenhouse", "token": "acme"}])["jobs"]
    assert [j["posted_at"] for j in jobs] == ["2026-08-01", "2026-07-20"]


def test_the_same_posting_from_two_boards_appears_once(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    result = jobfeed.collect([
        {"source": "greenhouse", "token": "acme"},
        {"source": "greenhouse", "token": "acme"},
    ])
    assert len(result["jobs"]) == 2


def test_preferences_are_applied_while_collecting(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    result = jobfeed.collect(
        [{"source": "greenhouse", "token": "acme"}], {"internships_only": True}
    )
    assert [j["title"] for j in result["jobs"]] == ["Backend Engineering Intern"]


def test_a_saved_label_overrides_the_board_name(stub):
    stub["greenhouse"] = GREENHOUSE_PAYLOAD
    result = jobfeed.collect(
        [{"source": "greenhouse", "token": "acme", "label": "Acme Labs India"}]
    )
    assert result["jobs"][0]["company"] == "Acme Labs India"
