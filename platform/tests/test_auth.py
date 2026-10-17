"""Day 12 and 14: registering, logging in, and the ways login can fail."""
import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from conftest import PASSWORD, new_client


def _email():
    return f"{uuid.uuid4().hex[:10]}@example.com"


def register(c, **over):
    body = {"business": "Asha Gifts " + uuid.uuid4().hex[:4], "name": "Asha", "email": _email(), "password": PASSWORD} | over
    return c.post("/api/auth/register", json=body), body


def test_register_creates_a_pending_shop_and_logs_in(client):
    r, body = register(client)
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["role"] == "seller_admin" and me["tenant"]["status"] == "pending"
    assert client.get("/api/auth/me").json()["email"] == body["email"].lower()


def test_session_cookie_is_http_only(client):
    r, _ = register(client)
    assert "httponly" in r.headers["set-cookie"].lower()
    assert "samesite=lax" in r.headers["set-cookie"].lower()


def test_password_is_stored_hashed_never_plain(client):
    r, body = register(client)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == body["email"].lower()))
    assert u.password_hash.startswith("scrypt$") and PASSWORD not in u.password_hash


def test_email_is_case_insensitive(client):
    _, body = register(client, email="Mixed.Case@Example.com")
    other = new_client()
    assert other.post("/api/auth/login", json={"email": "mixed.case@example.COM", "password": PASSWORD}).status_code == 200


def test_duplicate_email_is_refused(client):
    _, body = register(client)
    r, _ = register(new_client(), email=body["email"])
    assert r.status_code == 409


def test_weak_passwords_are_refused(client):
    for bad in ("short1", "password123", "aaaaaaaaaaaa"):
        r, _ = register(new_client(), password=bad)
        assert r.status_code == 422, bad
    r, body = register(new_client(), password="x" * 201)
    assert r.status_code == 422


def test_bad_email_is_refused(client):
    r, _ = register(client, email="not-an-email")
    assert r.status_code == 422


def test_reserved_and_taken_shop_names_are_refused(client):
    r, _ = register(client, slug="admin")
    assert r.status_code == 422
    r1, _ = register(new_client(), slug=f"shop-{uuid.uuid4().hex[:6]}")
    slug = r1.json()["tenant"]["slug"]
    r2, _ = register(new_client(), slug=slug)
    assert r2.status_code == 409


def test_shop_link_name_is_made_unique_automatically(client):
    name = "Same Name " + uuid.uuid4().hex[:4]
    a, _ = register(new_client(), business=name)
    b, _ = register(new_client(), business=name)
    assert a.json()["tenant"]["slug"] != b.json()["tenant"]["slug"]


def test_login_and_logout(client):
    _, body = register(client)
    c = new_client()
    r = c.post("/api/auth/login", json={"email": body["email"], "password": PASSWORD})
    assert r.status_code == 200 and c.get("/api/auth/me").json()["email"] == body["email"].lower()
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").json() is None


def test_wrong_password_and_unknown_email_look_identical(client):
    _, body = register(client)
    wrong = new_client().post("/api/auth/login", json={"email": body["email"], "password": "wrong-password-1"})
    unknown = new_client().post("/api/auth/login", json={"email": _email(), "password": "wrong-password-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()        # nothing reveals which emails have accounts


def test_repeated_wrong_passwords_are_slowed_down(client):
    _, body = register(client)
    codes = [new_client().post("/api/auth/login", json={"email": body["email"], "password": f"guess-number-{i}"}).status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[10] == 429
    # Even the right password is refused while the limit is active.
    assert new_client().post("/api/auth/login", json={"email": body["email"], "password": PASSWORD}).status_code == 429


def test_changes_need_the_request_header(client):
    from fastapi.testclient import TestClient
    from app.main import app
    bare = TestClient(app)        # no x-requested-with header, like a forged cross-site form post
    r = bare.post("/api/auth/login", json={"email": "a@b.co", "password": "whatever-1234"})
    assert r.status_code == 403


def test_expired_session_is_ignored(client):
    from datetime import datetime, timedelta, timezone
    from app.models import AuthSession
    register(client)
    with SessionLocal() as db:
        for s in db.scalars(select(AuthSession)):
            s.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/auth/me").json() is None
