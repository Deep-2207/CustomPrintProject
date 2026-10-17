"""Day 15: the platform owner approves sellers."""
from conftest import make_seller


def test_owner_sees_pending_sellers_and_approves_them(owner):
    s = make_seller(owner, business="Approval Test", approve=False)
    pending = {t["id"]: t for t in owner.get("/api/owner/tenants?status=pending").json()}
    t = pending[s.me["tenant"]["id"]]
    assert t["status"] == "pending" and t["email"] == s.email.lower() and t["products"] == 0
    assert owner.post(f"/api/owner/tenants/{t['id']}/status", json={"status": "active"}).json()["status"] == "active"
    assert t["id"] not in {x["id"] for x in owner.get("/api/owner/tenants?status=pending").json()}
    assert s.get("/api/auth/me").json()["tenant"]["status"] == "active"


def test_unknown_status_and_unknown_seller_are_refused(owner):
    s = make_seller(owner)
    assert owner.post(f"/api/owner/tenants/{s.me['tenant']['id']}/status", json={"status": "banana"}).status_code == 422
    assert owner.post("/api/owner/tenants/999999/status", json={"status": "active"}).status_code == 404


def test_owner_list_does_not_leak_password_hashes(owner):
    make_seller(owner)
    text = owner.get("/api/owner/tenants").text
    assert "scrypt" not in text and "password" not in text.lower()
