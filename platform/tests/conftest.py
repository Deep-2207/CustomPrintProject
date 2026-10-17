"""Test setup.

Runs against SQLite by default. To test on PostgreSQL:
    set TEST_DATABASE_URL=postgresql+psycopg2://postgres@localhost:5432/customizer_test   (an empty database; its tables are dropped first)
Every test gets fresh rate limits; tests create their own accounts with unique e-mail addresses.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp(prefix="customizer-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["OWNER_EMAIL"] = "owner@example.com"
os.environ["OWNER_PASSWORD"] = "Owner-test-password-2026"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402
from app.security import hash_password, limiter  # noqa: E402

PASSWORD = "A-long-test-passphrase-1"


@pytest.fixture(scope="session", autouse=True)
def _fresh_database():
    Base.metadata.drop_all(engine)
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS alembic_version"))
    yield


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


def new_client() -> TestClient:
    """A browser-like client with its own cookie jar. Sends the header the app requires on changes."""
    c = TestClient(app, headers={"x-requested-with": "fetch"})
    return c


@pytest.fixture(scope="session")
def app_started():
    with TestClient(app):          # runs start-up: migrations, built-in products, owner account
        yield


@pytest.fixture()
def client(app_started):
    return new_client()


@pytest.fixture()
def owner(app_started):
    c = new_client()
    r = c.post("/api/auth/login", json={"email": "owner@example.com", "password": "Owner-test-password-2026"})
    assert r.status_code == 200, r.text
    return c


def make_seller(owner_client, business="Test Shop", approve=True, role="seller_admin"):
    """Registers a seller (logged in on the returned client). Approves the account unless approve=False."""
    c = new_client()
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    r = c.post("/api/auth/register", json={"business": f"{business} {uuid.uuid4().hex[:5]}", "name": "Asha", "email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    me = r.json()
    if approve:
        assert owner_client.post(f"/api/owner/tenants/{me['tenant']['id']}/status", json={"status": "active"}).status_code == 200
        me = c.get("/api/auth/me").json()
    c.me = me
    c.email = email
    return c


def add_staff(tenant_id: int) -> TestClient:
    """A second login for the same shop with the limited 'seller_staff' role."""
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    with SessionLocal() as db:
        db.add(User(tenant_id=tenant_id, email=email, name="Staff", password_hash=hash_password(PASSWORD), role="seller_staff"))
        db.commit()
    c = new_client()
    assert c.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    return c


def make_glb(meshes=(("Cup", True),), triangles=12):
    """Builds a tiny valid .glb in memory. meshes = [(name, has_uv), ...]"""
    import json
    import struct
    accessors, mesh_list = [{"count": triangles * 3}, {"count": triangles * 3}], []
    for name, uv in meshes:
        attrs = {"POSITION": 0, "NORMAL": 1}
        if uv:
            attrs["TEXCOORD_0"] = 1
        mesh_list.append({"name": name, "primitives": [{"attributes": attrs, "indices": 0}]})
    doc = {"asset": {"version": "2.0"}, "accessors": accessors, "meshes": mesh_list, "nodes": [{"name": n, "mesh": i} for i, (n, _) in enumerate(meshes)]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body
