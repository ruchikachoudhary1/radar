"""
Tests for accounts, password handling and per-user data isolation.

The isolation tests matter most: they are the ones that would catch a route
where the user filter was forgotten and one account could read another's
resumes.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Point at a throwaway database before anything imports the engine.
_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["JWT_SECRET"] = "test-secret-not-used-anywhere-real"

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
import db as db_module  # noqa: E402
import main  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _schema():
    db_module.init_db()
    yield


@pytest.fixture()
def client():
    return TestClient(main.app)


def register(client, email, password="correct-horse-battery"):
    return client.post(
        "/api/auth/signup", json={"email": email, "password": password, "name": "Test"}
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Password handling
# --------------------------------------------------------------------------
def test_hash_is_not_the_password_and_verifies():
    digest = auth.hash_password("hunter2-hunter2")
    assert digest != "hunter2-hunter2"
    assert auth.verify_password("hunter2-hunter2", digest)
    assert not auth.verify_password("wrong", digest)


def test_same_password_gets_different_hashes():
    """bcrypt salts each digest, so identical passwords are not identical rows."""
    assert auth.hash_password("same-password-x") != auth.hash_password("same-password-x")


def test_verify_rejects_a_corrupt_hash_instead_of_raising():
    assert not auth.verify_password("anything", "not-a-bcrypt-hash")


# --------------------------------------------------------------------------
# Signup and login
# --------------------------------------------------------------------------
def test_signup_returns_a_token_and_never_the_hash(client):
    res = register(client, "alice@example.com")
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    assert body["user"]["email"] == "alice@example.com"
    assert "password" not in str(body).lower() or "password_hash" not in body["user"]


def test_duplicate_email_is_rejected(client):
    register(client, "dupe@example.com")
    assert register(client, "dupe@example.com").status_code == 409


def test_email_is_normalised_so_case_cannot_duplicate_an_account(client):
    register(client, "Case@Example.com")
    assert register(client, "case@example.com").status_code == 409


@pytest.mark.parametrize("email", ["not-an-email", "no@tld", "", "a b@c.com"])
def test_invalid_emails_are_rejected(client, email):
    assert register(client, email).status_code == 400


def test_short_passwords_are_rejected(client):
    res = client.post("/api/auth/signup", json={"email": "shorty@example.com", "password": "abc"})
    assert res.status_code == 400


def test_login_succeeds_and_wrong_password_fails(client):
    register(client, "bob@example.com", "my-real-password")
    ok = client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "my-real-password"}
    )
    assert ok.status_code == 200 and ok.json()["token"]

    bad = client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "guess"}
    )
    assert bad.status_code == 401


def test_login_does_not_reveal_whether_an_email_is_registered(client):
    register(client, "known@example.com", "the-right-password")
    wrong_pw = client.post(
        "/api/auth/login", json={"email": "known@example.com", "password": "nope"}
    )
    no_user = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"]


# --------------------------------------------------------------------------
# Token handling
# --------------------------------------------------------------------------
def test_protected_route_rejects_missing_and_malformed_tokens(client):
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Basic abc"}).status_code == 401


def test_token_signed_with_another_secret_is_rejected(client):
    import jwt

    forged = jwt.encode({"sub": "1"}, "a-different-secret", algorithm="HS256")
    assert client.get("/api/profile", headers=bearer(forged)).status_code == 401


def test_me_returns_the_signed_in_account(client):
    token = register(client, "me@example.com").json()["token"]
    res = client.get("/api/auth/me", headers=bearer(token))
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "me@example.com"


def test_health_stays_public(client):
    assert client.get("/api/health").status_code == 200


# --------------------------------------------------------------------------
# Per-user isolation — the tests that matter
# --------------------------------------------------------------------------
def test_one_user_cannot_see_anothers_applications(client):
    a = register(client, "owner@example.com").json()["token"]
    b = register(client, "stranger@example.com").json()["token"]

    created = client.post(
        "/api/applications",
        json={"text": "Backend Intern at Acme. Python and FastAPI. " * 10,
              "generate_resume": False},
        headers=bearer(a),
    )
    assert created.status_code == 200
    app_id = created.json()["id"]

    # The owner sees it; the stranger's list is empty and direct access 404s.
    assert any(i["id"] == app_id for i in client.get("/api/applications", headers=bearer(a)).json()["items"])
    assert client.get("/api/applications", headers=bearer(b)).json()["items"] == []
    assert client.get(f"/api/applications/{app_id}", headers=bearer(b)).status_code == 404


def test_one_user_cannot_modify_or_delete_anothers_application(client):
    a = register(client, "owner2@example.com").json()["token"]
    b = register(client, "stranger2@example.com").json()["token"]

    app_id = client.post(
        "/api/applications",
        json={"text": "Data Intern at Beta. SQL and Python. " * 10, "generate_resume": False},
        headers=bearer(a),
    ).json()["id"]

    assert client.patch(
        f"/api/applications/{app_id}", json={"status": "Offer"}, headers=bearer(b)
    ).status_code == 404
    assert client.delete(f"/api/applications/{app_id}", headers=bearer(b)).status_code == 404

    # And the owner's record is untouched.
    assert client.get(f"/api/applications/{app_id}", headers=bearer(a)).json()["status"] == "Saved"


def test_profiles_are_separate_per_user(client):
    a = register(client, "p1@example.com").json()["token"]
    b = register(client, "p2@example.com").json()["token"]

    client.put("/api/profile", json={"profile": {"name": "Alice", "skills": ["Python"]}},
               headers=bearer(a))
    client.put("/api/profile", json={"profile": {"name": "Bob", "skills": ["Java"]}},
               headers=bearer(b))

    assert client.get("/api/profile", headers=bearer(a)).json()["profile"]["name"] == "Alice"
    assert client.get("/api/profile", headers=bearer(b)).json()["profile"]["name"] == "Bob"


def test_a_new_account_starts_empty(client):
    token = register(client, "fresh@example.com").json()["token"]
    assert client.get("/api/applications", headers=bearer(token)).json()["items"] == []
    assert client.get("/api/history", headers=bearer(token)).json()["items"] == []
    assert client.get("/api/profile", headers=bearer(token)).json()["usable"] is False


def test_invalid_status_is_rejected(client):
    token = register(client, "status@example.com").json()["token"]
    app_id = client.post(
        "/api/applications",
        json={"text": "Intern at Gamma. Python. " * 10, "generate_resume": False},
        headers=bearer(token),
    ).json()["id"]
    assert client.patch(
        f"/api/applications/{app_id}", json={"status": "Hired!"}, headers=bearer(token)
    ).status_code == 400


def test_applying_stamps_the_date_for_the_follow_up_timer(client):
    token = register(client, "stamp@example.com").json()["token"]
    app_id = client.post(
        "/api/applications",
        json={"text": "Intern at Delta. Python. " * 10, "generate_resume": False},
        headers=bearer(token),
    ).json()["id"]

    assert client.get(f"/api/applications/{app_id}", headers=bearer(token)).json()["applied_at"] is None
    client.patch(f"/api/applications/{app_id}", json={"status": "Applied"}, headers=bearer(token))
    assert client.get(f"/api/applications/{app_id}", headers=bearer(token)).json()["applied_at"]


# --------------------------------------------------------------------------
# Deadline field and the follow-up clock
# --------------------------------------------------------------------------
def _new_app(client, token, **extra):
    payload = {"text": "Intern at Epsilon. Python. " * 10, "generate_resume": False}
    payload.update(extra)
    return client.post("/api/applications", json=payload, headers=bearer(token))


def test_a_deadline_round_trips(client):
    token = register(client, "dl1@example.com").json()["token"]
    res = _new_app(client, token, deadline="2026-09-30")
    assert res.status_code == 200
    assert res.json()["deadline"] == "2026-09-30"
    assert client.get(f"/api/applications/{res.json()['id']}",
                      headers=bearer(token)).json()["deadline"] == "2026-09-30"


def test_a_deadline_can_be_added_later_and_cleared(client):
    token = register(client, "dl2@example.com").json()["token"]
    app_id = _new_app(client, token).json()["id"]

    client.patch(f"/api/applications/{app_id}", json={"deadline": "2026-10-01"},
                 headers=bearer(token))
    assert client.get(f"/api/applications/{app_id}",
                      headers=bearer(token)).json()["deadline"] == "2026-10-01"

    client.patch(f"/api/applications/{app_id}", json={"deadline": ""}, headers=bearer(token))
    assert client.get(f"/api/applications/{app_id}", headers=bearer(token)).json()["deadline"] == ""


@pytest.mark.parametrize("bad", ["30-09-2026", "next friday", "2026-13-01", "2026-02-30"])
def test_an_unparseable_deadline_is_rejected(client, bad):
    """A date the colouring cannot read would silently never fire, so reject it."""
    token = register(client, f"dl-{abs(hash(bad))}@example.com").json()["token"]
    assert _new_app(client, token, deadline=bad).status_code == 400


def test_the_list_carries_an_urgency_verdict(client):
    token = register(client, "urg1@example.com").json()["token"]
    _new_app(client, token)
    item = client.get("/api/applications", headers=bearer(token)).json()["items"][0]
    assert item["urgency"] == {"level": "neutral", "label": "Not applied yet"}


def test_a_passed_deadline_shows_as_urgent_in_the_list(client):
    token = register(client, "urg2@example.com").json()["token"]
    _new_app(client, token, deadline="2020-01-01")
    item = client.get("/api/applications", headers=bearer(token)).json()["items"][0]
    assert item["urgency"]["level"] == "urgent"
    assert item["urgency"]["label"] == "Deadline passed"


def test_marking_replied_stops_the_clock(client):
    token = register(client, "urg3@example.com").json()["token"]
    app_id = _new_app(client, token).json()["id"]
    client.patch(f"/api/applications/{app_id}", json={"status": "Applied"}, headers=bearer(token))

    client.patch(f"/api/applications/{app_id}", json={"replied": True}, headers=bearer(token))
    item = client.get("/api/applications", headers=bearer(token)).json()["items"][0]
    assert item["replied"] is True
    assert item["urgency"] == {"level": "good", "label": "They replied"}
