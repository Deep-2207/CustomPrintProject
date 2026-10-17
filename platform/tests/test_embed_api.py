"""Days 21 to 23: public/secret keys, allowed websites, the embed page and its calls, and the server API."""
import uuid

import pytest

from conftest import add_staff, make_seller, new_client
from app import keys


def live_product(c, template="custom-printed-mug"):
    slug = f"mug-{uuid.uuid4().hex[:6]}"
    r = c.post("/api/seller/products", json={"name": "Mug", "slug": slug, "template": template})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert c.post(f"/api/seller/products/{pid}/publish", json={"published": True}).status_code == 200
    return pid, slug


def design(slug, **over):
    return {"slug": slug, "size": "11oz", "body_color": "#f4f4f4", "layers": [
        {"zone": "front", "type": "text", "text": "Deep", "font": "Arial", "template": "plain", "x": .5, "y": .5, "size": .5}]} | over


# ------------------------------------------------------------ website list rules (no server needed)
def test_domains_are_cleaned_up():
    assert keys.normalise_domain(" https://Shop.Example.com/cart?x=1 ") == "shop.example.com"
    assert keys.normalise_domain("*.example.com") == "*.example.com"
    assert keys.normalise_domain("localhost:3000") == "localhost:3000"
    for bad in ("not a domain", "javascript:alert(1)", "example", "a b.com", "*.*.com", "https://", "exa_mple.com", "'; frame-ancestors *"):
        with pytest.raises(ValueError):
            keys.normalise_domain(bad)
    assert keys.clean_domains(["a.com", "A.com", "", "b.com"]) == ["a.com", "b.com"]
    with pytest.raises(ValueError):
        keys.clean_domains([f"s{i}.example.com" for i in range(11)])


def test_origin_matching_is_exact_and_wildcards_do_not_overreach():
    d = ["shop.example.com", "*.partner.in", "localhost:3000"]
    assert keys.origin_allowed(d, "https://shop.example.com")
    assert not keys.origin_allowed(d, "http://shop.example.com")           # plain http is not allowed for real domains
    assert not keys.origin_allowed(d, "https://evil.com")
    assert not keys.origin_allowed(d, "https://shop.example.com.evil.com")
    assert not keys.origin_allowed(d, "https://notshop.example.com")
    assert keys.origin_allowed(d, "https://a.partner.in")
    assert not keys.origin_allowed(d, "https://partner.in")                # the wildcard needs a subdomain
    assert not keys.origin_allowed(d, "https://a.b.partner.in")            # and only one level
    assert not keys.origin_allowed(d, "https://evilpartner.in")
    assert keys.origin_allowed(d, "http://localhost:3000") and not keys.origin_allowed(d, "http://localhost:4000")
    assert keys.frame_ancestors([]) == "frame-ancestors 'self'"
    assert "https://shop.example.com" in keys.frame_ancestors(["shop.example.com"])


# ------------------------------------------------------------ settings and keys
def test_a_shop_gets_a_stable_public_key_and_staff_cannot_change_settings(owner):
    a = make_seller(owner)
    s = a.get("/api/seller/settings").json()
    assert s["public_key"].startswith("pk_") and s["allowed_domains"] == [] and s["secret_keys"] == []
    assert a.get("/api/seller/settings").json()["public_key"] == s["public_key"]
    staff = add_staff(a.me["tenant"]["id"])
    assert staff.get("/api/seller/settings").status_code == 200
    assert staff.put("/api/seller/settings/domains", json={"domains": ["x.com"]}).status_code == 403
    assert staff.post("/api/seller/keys", json={"kind": "secret"}).status_code == 403


def test_saving_websites(owner):
    a = make_seller(owner)
    r = a.put("/api/seller/settings/domains", json={"domains": ["https://Shop.Example.com/", "shop.example.com", "*.example.in"]})
    assert r.status_code == 200 and r.json()["allowed_domains"] == ["shop.example.com", "*.example.in"]
    r = a.put("/api/seller/settings/domains", json={"domains": ["fine.com", "bad one"]})
    assert r.status_code == 422 and "valid website" in r.json()["detail"]["errors"][0]
    assert a.get("/api/seller/settings").json()["allowed_domains"] == ["shop.example.com", "*.example.in"]   # the bad save changed nothing


def test_a_pending_shop_cannot_change_settings(owner):
    a = make_seller(owner, approve=False)
    assert a.get("/api/seller/settings").status_code == 200
    assert a.put("/api/seller/settings/domains", json={"domains": ["x.com"]}).status_code == 403


def test_secret_keys_are_shown_once_and_limited(owner):
    a = make_seller(owner)
    r = a.post("/api/seller/keys", json={"kind": "secret"})
    assert r.status_code == 201
    raw = r.json()["new_secret"]
    assert raw.startswith("sk_") and len(raw) > 30
    listed = a.get("/api/seller/settings").json()
    assert "new_secret" not in listed and raw not in str(listed) and listed["secret_keys"][0]["prefix"] == raw[:10]
    from app.database import SessionLocal
    from app.models import ApiKey
    with SessionLocal() as db:
        assert db.query(ApiKey).filter(ApiKey.key_value == raw).count() == 0            # only a hash is stored
    for _ in range(2):
        assert a.post("/api/seller/keys", json={"kind": "secret"}).status_code == 201
    assert a.post("/api/seller/keys", json={"kind": "secret"}).status_code == 422       # three at most


def test_revoking_a_key_stops_it_and_other_shops_cannot_revoke_it(owner):
    a, b = make_seller(owner), make_seller(owner)
    raw = a.post("/api/seller/keys", json={"kind": "secret"}).json()["new_secret"]
    kid = a.get("/api/seller/settings").json()["secret_keys"][0]["id"]
    assert b.delete(f"/api/seller/keys/{kid}").status_code == 404
    assert new_client().get("/api/v1/products", headers={"Authorization": f"Bearer {raw}"}).status_code == 200
    assert a.delete(f"/api/seller/keys/{kid}").status_code == 200
    assert new_client().get("/api/v1/products", headers={"Authorization": f"Bearer {raw}"}).status_code == 401


def test_replacing_the_public_key_breaks_old_embeds(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    old = a.get("/api/seller/settings").json()["public_key"]
    assert new_client().get(f"/embed/{old}/{slug}").status_code == 200
    new = a.post("/api/seller/keys", json={"kind": "public"}).json()["public_key"]
    assert new != old
    assert new_client().get(f"/embed/{old}/{slug}").status_code == 404
    assert new_client().get(f"/embed/{new}/{slug}").status_code == 200


# ------------------------------------------------------------ the embed page
def test_the_embed_page_only_allows_the_listed_websites_to_frame_it(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    pk = a.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    r = s.get(f"/embed/{pk}/{slug}")
    assert r.status_code == 200
    assert r.headers["content-security-policy"].startswith("frame-ancestors 'self';")     # nobody listed: nobody may frame it
    assert "x-frame-options" not in {k.lower() for k in r.headers}                       # it would override frame-ancestors
    a.put("/api/seller/settings/domains", json={"domains": ["shop.example.com"]})
    csp = s.get(f"/embed/{pk}/{slug}").headers["content-security-policy"]
    assert "frame-ancestors 'self' https://shop.example.com;" in csp and "script-src 'self'" in csp
    assert "evil" not in csp


def test_the_embed_page_hides_unpublished_unknown_and_suspended(owner):
    a = make_seller(owner)
    pid, slug = live_product(a)
    pk = a.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    assert s.get(f"/embed/{pk}/no-such-product").status_code == 404
    assert s.get("/embed/pk_notarealkey123456/" + slug).status_code == 404
    assert s.get(f"/embed/{pk}/..%2F..%2Fetc").status_code == 404
    a.post(f"/api/seller/products/{pid}/publish", json={"published": False})
    assert s.get(f"/embed/{pk}/{slug}").status_code == 404
    assert s.get(f"/api/embed/{pk}/products/{slug}").status_code == 404
    a.post(f"/api/seller/products/{pid}/publish", json={"published": True})
    assert s.get(f"/embed/{pk}/{slug}").status_code == 200
    owner.post(f"/api/owner/tenants/{a.me['tenant']['id']}/status", json={"status": "suspended"})
    assert s.get(f"/embed/{pk}/{slug}").status_code == 404
    assert s.get(f"/api/embed/{pk}/products/{slug}").status_code == 404


def test_a_key_only_opens_its_own_shops_products(owner):
    a, b = make_seller(owner), make_seller(owner)
    _, slug_a = live_product(a)
    pkb = b.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    assert s.get(f"/embed/{pkb}/{slug_a}").status_code == 404
    assert s.post(f"/api/embed/{pkb}/designs", json=design(slug_a)).status_code == 404


def test_host_check_endpoint(owner):
    a = make_seller(owner)
    pk = a.get("/api/seller/settings").json()["public_key"]
    a.put("/api/seller/settings/domains", json={"domains": ["shop.example.com"]})
    s = new_client()
    assert s.get(f"/api/embed/{pk}/host", params={"origin": "https://shop.example.com"}).json() == {"allowed": True}
    assert s.get(f"/api/embed/{pk}/host", params={"origin": "https://evil.com"}).json() == {"allowed": False}
    assert s.get(f"/api/embed/{pk}/host").json() == {"allowed": False}


def test_saving_a_design_through_the_embed(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    pk = a.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    no_header = new_client()
    no_header.headers.pop("x-requested-with")
    assert no_header.post(f"/api/embed/{pk}/designs", json=design(slug)).status_code == 403
    r = s.post(f"/api/embed/{pk}/designs", json=design(slug, ref="ORDER-1042"))
    assert r.status_code == 200, r.text
    row = a.get("/api/seller/designs").json()["designs"][0]
    assert row["id"] == r.json()["id"] and row["source"] == "embed" and row["ref"] == "ORDER-1042" and row["billable"] is True
    assert a.get("/api/seller/usage").json()["totals"]["design"] == 1
    # the seller trying it out inside their own dashboard is a preview: saved, never charged
    r2 = a.post(f"/api/embed/{pk}/designs", json=design(slug))
    assert r2.status_code == 200
    assert a.get("/api/seller/usage").json()["totals"]["design"] == 1
    assert next(d for d in a.get("/api/seller/designs").json()["designs"] if d["id"] == r2.json()["id"])["source"] == "preview"


def test_embed_rejects_a_bad_design_like_the_normal_page(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    pk = a.get("/api/seller/settings").json()["public_key"]
    bad = design(slug)
    bad["layers"][0]["text"] = "x" * 400
    assert new_client().post(f"/api/embed/{pk}/designs", json=bad).status_code == 422
    assert new_client().post(f"/api/embed/{pk}/designs", json=design(slug, ref="x" * 200)).status_code == 422


# ------------------------------------------------------------ server API with a secret key
def bearer(raw):
    return {"Authorization": f"Bearer {raw}"}


def test_api_needs_a_valid_secret_key(owner):
    a = make_seller(owner)
    pk = a.get("/api/seller/settings").json()["public_key"]
    s = new_client()
    assert s.get("/api/v1/designs").status_code == 401
    assert s.get("/api/v1/designs", headers=bearer("sk_" + "a" * 43)).status_code == 401
    assert s.get("/api/v1/designs", headers=bearer(pk)).status_code == 401           # the public key is not a password
    assert s.get("/api/v1/designs", headers={"Authorization": "Basic abc"}).status_code == 401


def test_api_shows_only_the_keys_own_shop(owner):
    a, b = make_seller(owner), make_seller(owner)
    _, slug_a = live_product(a)
    _, slug_b = live_product(b)
    ka, kb = a.post("/api/seller/keys", json={"kind": "secret"}).json()["new_secret"], b.post("/api/seller/keys", json={"kind": "secret"}).json()["new_secret"]
    pka, pkb = (c.get("/api/seller/settings").json()["public_key"] for c in (a, b))
    da = new_client().post(f"/api/embed/{pka}/designs", json=design(slug_a, ref="A-1")).json()["id"]
    db_ = new_client().post(f"/api/embed/{pkb}/designs", json=design(slug_b, ref="B-1")).json()["id"]
    s = new_client()
    assert [d["id"] for d in s.get("/api/v1/designs", headers=bearer(ka)).json()] == [da]
    assert [d["id"] for d in s.get("/api/v1/designs", headers=bearer(kb)).json()] == [db_]
    assert s.get(f"/api/v1/designs/{db_}", headers=bearer(ka)).status_code == 404
    one = s.get(f"/api/v1/designs/{da}", headers=bearer(ka)).json()
    assert one["ref"] == "A-1" and one["text"] == "Deep" and one["design"]["layers"][0]["text"] == "Deep" and one["preview_url"].endswith(f"/{da}.png")
    assert [d["id"] for d in s.get("/api/v1/designs", params={"ref": "A-1"}, headers=bearer(ka)).json()] == [da]
    assert s.get("/api/v1/designs", params={"ref": "B-1"}, headers=bearer(ka)).json() == []
    assert s.get("/api/v1/designs", params={"before": db_}, headers=bearer(ka)).status_code == 404      # cannot probe another shop's ids
    assert [p["slug"] for p in s.get("/api/v1/products", headers=bearer(ka)).json()] == [slug_a]
    assert s.get("/api/v1/designs/not-an-id", headers=bearer(ka)).status_code == 404


def test_api_paging(owner):
    a = make_seller(owner)
    _, slug = live_product(a)
    k = a.post("/api/seller/keys", json={"kind": "secret"}).json()["new_secret"]
    pk = a.get("/api/seller/settings").json()["public_key"]
    ids = [new_client().post(f"/api/embed/{pk}/designs", json=design(slug)).json()["id"] for _ in range(5)]
    s = new_client()
    seen, before = [], None
    for _ in range(5):
        page = s.get("/api/v1/designs", params={"limit": 2, **({"before": before} if before else {})}, headers=bearer(k)).json()
        if not page:
            break
        seen += [d["id"] for d in page]
        before = page[-1]["id"]
    assert sorted(seen) == sorted(ids) and len(seen) == len(set(seen)) == 5


def test_guessing_keys_is_slowed_down(owner):
    s = new_client()
    codes = [s.get("/api/v1/designs", headers=bearer("sk_" + uuid.uuid4().hex * 2)).status_code for _ in range(33)]
    assert codes[0] == 401 and codes[-1] == 429


def test_a_suspended_shops_keys_stop_working(owner):
    a = make_seller(owner)
    k = a.post("/api/seller/keys", json={"kind": "secret"}).json()["new_secret"]
    owner.post(f"/api/owner/tenants/{a.me['tenant']['id']}/status", json={"status": "suspended"})
    assert new_client().get("/api/v1/products", headers=bearer(k)).status_code == 401
