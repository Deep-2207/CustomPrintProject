"""Day 28: security headers, password change, and a few hard cases."""
from conftest import PASSWORD, make_seller, new_client
from test_embed_api import design, live_product


def test_every_page_and_api_answer_carries_the_security_headers(client):
    for path in ("/", "/api/auth/me", "/account.html", "/healthz"):
        r = client.get(path)
        h = {k.lower(): v for k, v in r.headers.items()}
        assert h["x-content-type-options"] == "nosniff", path
        assert h["referrer-policy"], path
        assert "script-src 'self'" in h["content-security-policy"] and "frame-ancestors 'self'" in h["content-security-policy"], path
        assert "object-src 'none'" in h["content-security-policy"], path
        assert h["x-frame-options"] == "SAMEORIGIN", path
        assert "camera=()" in h["permissions-policy"], path


def test_no_page_uses_inline_scripts_or_handlers():
    """The policy blocks them, so a page that used one would silently break. Catch it here instead."""
    import re
    from pathlib import Path
    for f in (Path(__file__).resolve().parent.parent / "static").glob("*.html"):
        html = f.read_text(encoding="utf8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), f"{f.name} has an inline script"
        assert not re.search(r"\son(click|change|load|error|submit|input)=", html), f"{f.name} has an inline event handler"


def test_health_check(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_changing_your_password(owner):
    a = make_seller(owner)
    other_device = new_client()
    assert other_device.post("/api/auth/login", json={"email": a.email, "password": PASSWORD}).status_code == 200
    assert other_device.get("/api/auth/me").json() is not None
    assert a.post("/api/auth/password", json={"current": "wrong-wrong-wrong", "new": "A-brand-new-passphrase-9"}).status_code == 403
    assert a.post("/api/auth/password", json={"current": PASSWORD, "new": "short"}).status_code == 422
    assert a.post("/api/auth/password", json={"current": PASSWORD, "new": a.email}).status_code == 422
    assert a.post("/api/auth/password", json={"current": PASSWORD, "new": "A-brand-new-passphrase-9"}).status_code == 200
    assert a.get("/api/auth/me").json() is not None                           # this device stays logged in
    assert other_device.get("/api/auth/me").json() is None                    # every other device is logged out
    assert new_client().post("/api/auth/login", json={"email": a.email, "password": PASSWORD}).status_code == 401
    assert new_client().post("/api/auth/login", json={"email": a.email, "password": "A-brand-new-passphrase-9"}).status_code == 200


def test_password_change_needs_login_and_the_forgery_header(owner):
    assert new_client().post("/api/auth/password", json={"current": "x", "new": "y"}).status_code == 401
    a = make_seller(owner)
    a.headers.pop("x-requested-with")
    assert a.post("/api/auth/password", json={"current": PASSWORD, "new": "A-brand-new-passphrase-9"}).status_code == 403


def test_password_change_attempts_are_limited(owner):
    a = make_seller(owner)
    codes = [a.post("/api/auth/password", json={"current": "nope-nope-nope", "new": "A-brand-new-passphrase-9"}).status_code for _ in range(12)]
    assert codes[0] == 403 and codes[-1] == 429


def test_a_strange_admin_key_header_does_not_crash(client):
    assert client.get("/api/leads", headers={"x-admin-key": "café".encode("utf-8")}).status_code == 401


def test_every_new_state_changing_route_wants_the_forgery_header(owner):
    a = make_seller(owner)
    pid, slug = live_product(a)
    a.headers.pop("x-requested-with")
    for method, url, body in (("put", "/api/seller/settings/domains", {"domains": ["a.com"]}), ("post", "/api/seller/keys", {"kind": "secret"}),
                              ("delete", "/api/seller/keys/1", None), ("post", "/api/seller/designs/aaaaaaaaaaaa/exported", None)):
        r = getattr(a, method)(url, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (url, r.status_code)


def test_an_oversized_preview_picture_is_refused(client):
    r = client.post("/api/designs", json=design("custom-printed-mug", preview_png="data:image/png;base64," + "A" * 4_600_000))
    assert r.status_code == 422


def test_embed_save_and_host_check_are_rate_limited(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    pk = a.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    codes = [s.post(f"/api/embed/{pk}/designs", json=design(slug)).status_code for _ in range(62)]
    assert codes[0] == 200 and codes[-1] == 429


def test_one_shop_cannot_be_flooded_with_billable_designs(owner, monkeypatch):
    """The public key is in the page source: without a per-shop cap a script could run up the seller's bill."""
    monkeypatch.setattr("app.designs.TENANT_DESIGNS_PER_HOUR", 3)
    a, b = make_seller(owner), make_seller(owner)
    _, slug = live_product(a)
    _, slug_b = live_product(b)
    pk, pkb = (c.get("/api/seller/settings").json()["public_key"] for c in (a, b))
    codes = [new_client().post(f"/api/embed/{pk}/designs", json=design(slug)).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert a.get("/api/seller/usage").json()["totals"]["design"] == 3            # refused designs are not saved or charged
    assert new_client().post(f"/api/embed/{pkb}/designs", json=design(slug_b)).status_code == 200   # another shop is unaffected
    assert a.post(f"/api/embed/{pk}/designs", json=design(slug)).status_code == 200                  # the seller testing is never capped or charged
