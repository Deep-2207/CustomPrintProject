"""Days 24 to 27: the designs list, usage counting, plans and invoices."""
import csv
import io
import time
import uuid

from conftest import add_staff, make_seller, new_client
from app import billing
from app.models import Tenant
from test_embed_api import design, live_product


def shop_with_product(owner):
    a = make_seller(owner)
    pid, slug = live_product(a)
    return a, pid, slug, a.me["tenant"]["slug"]


def shopper_saves(seller_slug, slug, text="Deep", **over):
    d = design(slug, seller=seller_slug, **over)
    d["layers"][0]["text"] = text
    r = new_client().post("/api/designs", json=d)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ------------------------------------------------------------ designs list
def test_designs_list_search_filter_and_paging(owner):
    a, pid, slug, seller = shop_with_product(owner)
    pid2, slug2 = live_product(a)
    ids = [shopper_saves(seller, slug, text=f"Name {i}") for i in range(23)]
    time.sleep(0.05)                                                   # the Windows clock ticks about every 15 ms: keep "newest" unambiguous
    only = shopper_saves(seller, slug2, text="Special Tarun")
    r = a.get("/api/seller/designs").json()
    assert r["total"] == 24 and len(r["designs"]) == 20 and r["per_page"] == 20
    assert r["designs"][0]["id"] == only                               # newest first
    assert len(a.get("/api/seller/designs", params={"page": 2}).json()["designs"]) == 4
    assert [d["id"] for d in a.get("/api/seller/designs", params={"q": "tarun"}).json()["designs"]] == [only]
    assert [d["id"] for d in a.get("/api/seller/designs", params={"q": ids[3]}).json()["designs"]] == [ids[3]]
    assert a.get("/api/seller/designs", params={"product_id": pid2}).json()["total"] == 1
    assert a.get("/api/seller/designs", params={"q": "no-such-text"}).json()["total"] == 0
    row = a.get("/api/seller/designs", params={"q": "tarun"}).json()["designs"][0]
    assert row["text"] == "Special Tarun" and row["source"] == "share" and row["billable"] is True and row["preview"].endswith(f"{only}.png")


def test_a_shop_never_sees_another_shops_designs(owner):
    a, _, slug_a, seller_a = shop_with_product(owner)
    b = make_seller(owner)
    da = shopper_saves(seller_a, slug_a, text="Secret A")
    assert b.get("/api/seller/designs").json()["total"] == 0
    assert b.get("/api/seller/designs", params={"q": "Secret"}).json()["total"] == 0
    assert b.get(f"/api/seller/designs/{da}").status_code == 404
    assert b.post(f"/api/seller/designs/{da}/exported").status_code == 404
    assert a.get(f"/api/seller/designs/{da}").status_code == 200
    # a logged-out visitor sees none of it
    assert new_client().get("/api/seller/designs").status_code == 401
    assert new_client().get(f"/api/seller/designs/{da}").status_code == 401


def test_design_detail_has_what_the_print_page_needs(owner):
    a, _, slug, seller = shop_with_product(owner)
    did = shopper_saves(seller, slug, text="Deep\nPatel")
    d = a.get(f"/api/seller/designs/{did}").json()
    assert d["design"]["layers"][0]["text"] == "Deep\nPatel" and d["product_config"]["slug"] == slug
    assert any(z["id"] == "front" for z in d["product_config"]["zones"])


def test_zone_real_size_is_saved_and_validated(owner):
    a, pid, slug, _ = shop_with_product(owner)
    p = a.get(f"/api/seller/products/{pid}").json()["config"]
    body = {k: p[k] for k in ("name", "colors", "imprint_colors", "fonts", "zones", "defaults", "sample", "placeholder", "price")} | {"sizes": p.get("sizes", [])}
    body["zones"][0]["print_w_mm"], body["zones"][0]["print_h_mm"] = 90, 80
    assert a.put(f"/api/seller/products/{pid}", json=body).status_code == 200
    z = a.get(f"/api/seller/products/{pid}").json()["config"]["zones"][0]
    assert z["print_w_mm"] == 90 and z["print_h_mm"] == 80
    body["zones"][0]["print_w_mm"] = -5
    assert a.put(f"/api/seller/products/{pid}", json=body).status_code == 422


# ------------------------------------------------------------ usage counters
def test_views_designs_and_exports_are_counted_for_the_right_shop(owner):
    a, _, slug, seller = shop_with_product(owner)
    b = make_seller(owner)
    s = new_client()
    for _ in range(3):
        assert s.get(f"/api/t/{seller}/products/{slug}").status_code == 200
    a.get(f"/api/t/{seller}/products/{slug}")                            # the seller previewing is not a customer view
    did = shopper_saves(seller, slug)
    shopper_saves(seller, slug)
    assert a.post(f"/api/seller/designs/{did}/exported").status_code == 200
    t = a.get("/api/seller/usage").json()["totals"]
    assert t == {"view": 3, "design": 2, "export": 1}
    assert b.get("/api/seller/usage").json()["totals"] == {"view": 0, "design": 0, "export": 0}
    day = next(iter(a.get("/api/seller/usage").json()["days"].values()))
    assert day["design"] == 2


def test_a_design_by_the_seller_is_not_billed_and_platform_demos_are_not_counted(owner):
    a, _, slug, seller = shop_with_product(owner)
    d = design(slug, seller=seller)
    assert a.post("/api/designs", json=d).status_code == 200            # the seller testing their own product
    assert a.get("/api/seller/usage").json()["totals"]["design"] == 0
    assert new_client().post("/api/designs", json=design("custom-printed-mug")).status_code == 200   # platform demo product
    assert a.get("/api/seller/usage").json()["totals"]["design"] == 0


def test_usage_rejects_a_bad_month_and_an_old_month_is_empty(owner):
    a, _, slug, seller = shop_with_product(owner)
    shopper_saves(seller, slug)
    assert a.get("/api/seller/usage", params={"month": "2026-13"}).status_code == 422
    assert a.get("/api/seller/usage", params={"month": "'; drop table"}).status_code == 422
    assert a.get("/api/seller/usage", params={"month": "2020-01"}).json()["totals"]["design"] == 0


def test_staff_can_read_usage_but_not_download_the_invoice(owner):
    a, *_ = shop_with_product(owner)
    staff = add_staff(a.me["tenant"]["id"])
    assert staff.get("/api/seller/usage").status_code == 200
    assert staff.get("/api/seller/invoice.csv").status_code == 403
    assert a.get("/api/seller/invoice.csv").status_code == 200


def test_usage_counter_survives_many_saves():
    from app import usage
    from app.database import SessionLocal
    with SessionLocal() as db:
        t = Tenant(slug=f"u-{uuid.uuid4().hex[:8]}", name="U", status="active")
        db.add(t)
        db.commit()
        for _ in range(7):
            usage.bump(db, t.id, "design")
        assert usage.per_day(db, t.id, None)["totals"]["design"] == 7


# ------------------------------------------------------------ plan maths and invoices
def tenant(**kw):
    return Tenant(slug="x", name=kw.pop("name", "X"), status="active", **kw)


def test_pilot_is_free_and_starter_charges_extra_designs():
    assert billing.invoice(tenant(plan="pilot"), {"design": 500})["total"] == 0
    inv = billing.invoice(tenant(plan="starter"), {"design": 350, "view": 900})
    assert (inv["monthly_fee"], inv["extra_designs"], inv["extra_amount"], inv["subtotal"]) == (999, 50, 150, 1149)
    assert inv["gst"] == round(1149 * .18) and inv["total"] == 1149 + inv["gst"] and inv["views"] == 900
    assert billing.invoice(tenant(plan="starter"), {"design": 300})["extra_designs"] == 0     # included designs are free
    assert billing.invoice(tenant(plan="starter"), None)["total"] == round(999 * 1.18)


def test_setup_fee_is_charged_until_marked_paid():
    t = tenant(plan="starter", setup_fee=5000, setup_fee_paid=False)
    assert billing.invoice(t, {})["setup_fee"] == 5000 and billing.invoice(t, {})["subtotal"] == 5999
    t.setup_fee_paid = True
    assert billing.invoice(t, {})["subtotal"] == 999


def test_unknown_plan_falls_back_to_pilot():
    assert billing.invoice(tenant(plan="gone"), {"design": 10})["total"] == 0


def test_csv_neutralises_spreadsheet_formulas():
    rows = [(tenant(plan="starter", name='=HYPERLINK("http://evil")'), "2026-10", billing.invoice(tenant(plan="starter"), {}))]
    first = list(csv.reader(io.StringIO(billing.csv_text(rows))))[1][0]
    assert first.startswith("'=")


def test_owner_sets_plans_and_downloads_invoices(owner):
    a, _, slug, seller = shop_with_product(owner)
    for _ in range(3):
        shopper_saves(seller, slug)
    tid = a.me["tenant"]["id"]
    assert owner.post(f"/api/owner/tenants/{tid}/plan", json={"plan": "starter", "setup_fee": 2000}).status_code == 200
    assert owner.post(f"/api/owner/tenants/{tid}/plan", json={"plan": "platinum"}).status_code == 422
    assert owner.post(f"/api/owner/tenants/{tid}/plan", json={"plan": "starter", "setup_fee": -1}).status_code == 422
    row = next(t for t in owner.get("/api/owner/tenants").json() if t["id"] == tid)
    assert row["plan"] == "starter" and row["invoice"]["designs"] == 3 and row["invoice"]["setup_fee"] == 2000
    r = owner.get("/api/owner/invoice.csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"] and "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    mine = next(x for x in rows if x["shop_link"] == seller)
    assert mine["plan"] == "starter" and mine["designs"] == "3" and mine["setup_fee"] == "2000"
    assert int(mine["total"]) == round((999 + 2000) * 1.18)
    # the seller sees the same numbers
    inv = a.get("/api/seller/usage").json()["invoice"]
    assert inv["total"] == int(mine["total"])
    mycsv = list(csv.DictReader(io.StringIO(a.get("/api/seller/invoice.csv").text)))
    assert len(mycsv) == 1 and mycsv[0]["shop_link"] == seller


def test_only_the_owner_can_change_plans_or_download_all_invoices(owner):
    a, *_ = shop_with_product(owner)
    tid = a.me["tenant"]["id"]
    assert a.post(f"/api/owner/tenants/{tid}/plan", json={"plan": "growth"}).status_code == 403    # a seller cannot pick a cheaper plan
    assert a.get("/api/owner/invoice.csv").status_code == 403
    assert new_client().get("/api/owner/invoice.csv").status_code == 401
    assert a.get("/api/seller/usage").json()["plan"]["id"] == "pilot"
