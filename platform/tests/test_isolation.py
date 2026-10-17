"""Day 13 and 14: one seller must never see or change another seller's data."""
import uuid

from conftest import PASSWORD, add_staff, make_glb, make_seller, new_client


def clone(c, template="custom-printed-mug", slug=None, name="My mug"):
    r = c.post("/api/seller/products", json={"name": name, "slug": slug or f"mug-{uuid.uuid4().hex[:6]}", "template": template})
    assert r.status_code == 201, r.text
    return r.json()


def test_each_seller_sees_only_their_own_products(owner):
    a, b = make_seller(owner), make_seller(owner)
    pa, pb = clone(a), clone(b)
    ids_a = {p["id"] for p in a.get("/api/seller/products").json()}
    ids_b = {p["id"] for p in b.get("/api/seller/products").json()}
    assert ids_a == {pa["id"]} and ids_b == {pb["id"]}


def test_another_sellers_product_id_is_404_for_every_action(owner):
    a, b = make_seller(owner), make_seller(owner)
    pa = clone(a)
    pid = pa["id"]
    edit = {"name": "Hacked", "colors": pa["config"]["colors"], "fonts": ["Arial"], "zones": pa["config"]["zones"]}
    assert b.get(f"/api/seller/products/{pid}").status_code == 404
    assert b.put(f"/api/seller/products/{pid}", json=edit).status_code == 404
    assert b.post(f"/api/seller/products/{pid}/publish", json={"published": True}).status_code == 404
    assert b.delete(f"/api/seller/products/{pid}").status_code == 404
    # ...and it is untouched
    assert a.get(f"/api/seller/products/{pid}").json()["name"] == "My mug"


def test_the_same_link_name_can_be_used_by_two_sellers(owner):
    a, b = make_seller(owner), make_seller(owner)
    clone(a, slug="mug")
    clone(b, slug="mug")     # allowed: link names only need to be unique inside one shop
    assert a.post("/api/seller/products", json={"name": "x", "slug": "mug", "template": "custom-printed-mug"}).status_code == 409


def test_a_seller_cannot_use_another_sellers_3d_model(owner):
    a, b = make_seller(owner), make_seller(owner)
    up = a.post("/api/seller/models", files={"file": ("cup.glb", make_glb(), "model/gltf-binary")})
    assert up.status_code == 201, up.text
    mid = up.json()["id"]
    assert b.post("/api/seller/products", json={"name": "Steal", "slug": "steal", "model_id": mid}).status_code == 404
    assert b.get("/api/seller/models").json() == []
    assert a.post("/api/seller/products", json={"name": "Mine", "slug": "mine", "model_id": mid}).status_code == 201


def test_designs_belong_to_the_seller_whose_product_they_use(owner):
    a = make_seller(owner)
    p = clone(a)
    assert a.post(f"/api/seller/products/{p['id']}/publish", json={"published": True}).status_code == 200
    slug = a.me["tenant"]["slug"]
    shopper = new_client()
    r = shopper.post("/api/designs", json={"slug": p["slug"], "seller": slug, "size": "11oz", "body_color": "#f4f4f4", "layers": []})
    assert r.status_code == 200, r.text
    from app.database import SessionLocal
    from app.models import Design
    with SessionLocal() as db:
        d = db.get(Design, r.json()["id"])
        assert d.tenant_id == a.me["tenant"]["id"] and d.product_id == p["id"]


def test_unpublished_products_are_hidden_from_shoppers_but_not_from_the_seller(owner):
    a = make_seller(owner)
    p = clone(a)
    slug = a.me["tenant"]["slug"]
    url = f"/api/t/{slug}/products/{p['slug']}"
    shopper = new_client()
    assert shopper.get(url).status_code == 404
    assert shopper.get(f"/s/{slug}/{p['slug']}").status_code == 404
    assert a.get(url).status_code == 200                  # the seller previews their draft
    assert owner.get(url).status_code == 200              # so can the platform owner
    assert shopper.get(f"/api/t/{slug}/products").json() == []
    a.post(f"/api/seller/products/{p['id']}/publish", json={"published": True})
    assert shopper.get(url).status_code == 200
    assert shopper.get(f"/s/{slug}/{p['slug']}").status_code == 200
    assert [x["slug"] for x in shopper.get(f"/api/t/{slug}/products").json()] == [p["slug"]]


def test_another_sellers_draft_is_not_visible_to_a_different_seller(owner):
    a, b = make_seller(owner), make_seller(owner)
    p = clone(a)
    assert b.get(f"/api/t/{a.me['tenant']['slug']}/products/{p['slug']}").status_code == 404


def test_suspended_shop_disappears_for_shoppers(owner):
    a = make_seller(owner)
    p = clone(a)
    a.post(f"/api/seller/products/{p['id']}/publish", json={"published": True})
    slug = a.me["tenant"]["slug"]
    url = f"/api/t/{slug}/products/{p['slug']}"
    assert new_client().get(url).status_code == 200
    owner.post(f"/api/owner/tenants/{a.me['tenant']['id']}/status", json={"status": "suspended"})
    assert new_client().get(url).status_code == 404
    assert a.post("/api/seller/products", json={"name": "n", "slug": "new-one", "template": "custom-printed-mug"}).status_code == 403


def test_pending_shop_can_look_around_but_not_create(owner):
    a = make_seller(owner, approve=False)
    assert a.get("/api/seller/products").status_code == 200
    assert a.get("/api/seller/templates").status_code == 200
    r = a.post("/api/seller/products", json={"name": "n", "slug": "first", "template": "custom-printed-mug"})
    assert r.status_code == 403 and "approval" in r.json()["detail"]


def test_staff_can_read_but_not_change(owner):
    a = make_seller(owner)
    p = clone(a)
    staff = add_staff(a.me["tenant"]["id"])
    assert [x["id"] for x in staff.get("/api/seller/products").json()] == [p["id"]]
    assert staff.get(f"/api/seller/products/{p['id']}").status_code == 200
    assert staff.post("/api/seller/products", json={"name": "n", "slug": "staff-made", "template": "custom-printed-mug"}).status_code == 403
    assert staff.delete(f"/api/seller/products/{p['id']}").status_code == 403
    assert staff.post(f"/api/seller/products/{p['id']}/publish", json={"published": True}).status_code == 403


def test_logged_out_visitors_cannot_use_seller_or_owner_endpoints(client):
    assert client.get("/api/seller/products").status_code == 401
    assert client.post("/api/seller/products", json={"name": "n", "slug": "xx", "template": "custom-printed-mug"}).status_code == 401
    assert client.get("/api/owner/tenants").status_code == 401
    assert client.get("/api/seller/models").status_code == 401


def test_sellers_cannot_use_owner_endpoints(owner):
    a = make_seller(owner)
    assert a.get("/api/owner/tenants").status_code == 403
    assert a.post(f"/api/owner/tenants/{a.me['tenant']['id']}/status", json={"status": "active"}).status_code == 403
    assert a.get("/api/owner/leads").status_code == 403


def test_a_seller_cannot_approve_themselves(owner):
    a = make_seller(owner, approve=False)
    assert a.post(f"/api/owner/tenants/{a.me['tenant']['id']}/status", json={"status": "active"}).status_code == 403
    assert a.get("/api/auth/me").json()["tenant"]["status"] == "pending"
