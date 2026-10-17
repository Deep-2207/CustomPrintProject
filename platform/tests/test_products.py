"""Days 16 and 17: creating a product from a template and editing it."""
import copy
import uuid

from conftest import make_seller


def clone(c, template="custom-printed-mug", name="Mug"):
    r = c.post("/api/seller/products", json={"name": name, "slug": f"p-{uuid.uuid4().hex[:6]}", "template": template})
    assert r.status_code == 201, r.text
    return r.json()


def edit_body(p, **over):
    cfg = p["config"]
    body = {"name": cfg["name"], "sizes": cfg["sizes"], "colors": cfg["colors"], "imprint_colors": cfg["imprint_colors"], "fonts": cfg["fonts"],
            "zones": cfg["zones"], "defaults": cfg["defaults"], "sample": cfg["sample"], "placeholder": cfg["placeholder"], "price": cfg["price"]}
    return body | over


def test_templates_are_listed_for_sellers(owner):
    s = make_seller(owner)
    slugs = {t["slug"] for t in s.get("/api/seller/templates").json()}
    assert {"custom-printed-mug", "custom-embossed-wristband"} <= slugs


def test_clone_copies_the_template_as_an_unpublished_draft(owner):
    s = make_seller(owner)
    p = clone(s, name="  Photo Mug  ")
    assert p["name"] == "Photo Mug" and p["published"] is False
    assert p["config"]["model"]["template"] == "mug" and len(p["config"]["zones"]) == 2
    assert "seed_version" not in p["config"] and p["config"]["clone_of"] == "custom-printed-mug"


def test_editing_the_copy_does_not_change_the_template(owner):
    s = make_seller(owner)
    p = clone(s)
    body = edit_body(p, name="Renamed", colors=[{"name": "Teal", "hex": "#0d9488"}], defaults={"bodyColor": "#0d9488", "tpl": "script", "textSize": 0.5})
    assert s.put(f"/api/seller/products/{p['id']}", json=body).status_code == 200
    original = new_public().get("/api/products/custom-printed-mug").json()
    assert original["name"] == "Custom Printed Mugs" and len(original["colors"]) == 8


def new_public():
    from conftest import new_client
    return new_client()


def test_edit_saves_colours_fonts_zones_and_defaults(owner):
    s = make_seller(owner)
    p = clone(s)
    zones = copy.deepcopy(p["config"]["zones"])
    zones[0].update(max_chars=20, max_lines=2, style="print", allow_images=False, label="Left side")
    body = edit_body(p, colors=[{"name": "Teal", "hex": "#0D9488"}, {"name": "Cream", "hex": "#f5e6c8"}], fonts=["Impact", "Arial"], zones=zones,
                     defaults={"bodyColor": "#0d9488", "tpl": "badge", "textSize": 0.4, "font": "Impact"}, placeholder="Your name here", price={"base": 299})
    r = s.put(f"/api/seller/products/{p['id']}", json=body)
    assert r.status_code == 200, r.text
    c = s.get(f"/api/seller/products/{p['id']}").json()["config"]
    assert [x["hex"] for x in c["colors"]] == ["#0d9488", "#f5e6c8"]            # stored lower-case
    assert c["fonts"] == ["Impact", "Arial"] and c["zones"][0]["max_chars"] == 20 and c["zones"][0]["label"] == "Left side"
    assert c["defaults"] == {"bodyColor": "#0d9488", "tpl": "badge", "font": "Impact", "textSize": 0.4}
    assert c["placeholder"] == "Your name here" and c["price"]["base"] == 299


def test_bad_edits_are_refused_with_clear_messages(owner):
    s = make_seller(owner)
    p = clone(s)
    url = f"/api/seller/products/{p['id']}"
    def errors(**over):
        r = s.put(url, json=edit_body(p, **over))
        assert r.status_code == 422, r.text
        return " ".join(r.json()["detail"]["errors"]).lower()
    assert "colour" in errors(colors=[{"name": "Bad", "hex": "red"}])
    assert "at least one" in errors(colors=[])
    assert "same" in errors(colors=[{"name": "A", "hex": "#111111"}, {"name": "B", "hex": "#111111"}])
    assert "font" in errors(fonts=["Comic Sans"])
    assert "font" in errors(fonts=[])
    z = copy.deepcopy(p["config"]["zones"])
    z[1]["id"] = z[0]["id"]
    assert "share the id" in errors(zones=z)
    z = copy.deepcopy(p["config"]["zones"])
    z[0].update(u0=0.5, u1=0.51)
    assert "too small" in errors(zones=z)
    z = copy.deepcopy(p["config"]["zones"])
    z[0]["mesh"] = "not_a_part"
    assert "no part called" in errors(zones=z)
    assert "starting colour" in errors(defaults={"bodyColor": "#abcdef"})
    assert "text size" in errors(defaults={"textSize": 5})
    assert "style" in errors(defaults={"tpl": "evil"})
    assert "price" in errors(price={"base": "free"})


def test_edit_cannot_change_the_model_or_slug(owner):
    s = make_seller(owner)
    p = clone(s)
    body = edit_body(p) | {"model": {"type": "glb", "url": "/files/models/x.glb"}, "slug": "hijack"}
    assert s.put(f"/api/seller/products/{p['id']}", json=body).status_code == 200
    got = s.get(f"/api/seller/products/{p['id']}").json()
    assert got["config"]["model"]["template"] == "mug" and got["slug"] == p["slug"]


def test_markup_in_names_is_stripped(owner):
    s = make_seller(owner)
    p = clone(s)
    body = edit_body(p, colors=[{"name": "<b>Red</b>", "hex": "#ff0000"}], placeholder="<script>x</script>", defaults={"bodyColor": "#ff0000"})
    assert s.put(f"/api/seller/products/{p['id']}", json=body).status_code == 200
    c = s.get(f"/api/seller/products/{p['id']}").json()["config"]
    assert "<" not in c["colors"][0]["name"] and "<" not in c["placeholder"]


def test_sizes_can_be_renamed_but_not_reshaped(owner):
    s = make_seller(owner)
    p = clone(s)
    sizes = [{"id": "11oz", "label": "Small", "mm": 5, "radius": 5}, {"id": "bogus", "label": "Ghost", "mm": 1}]
    assert s.put(f"/api/seller/products/{p['id']}", json=edit_body(p, sizes=sizes)).status_code == 200
    got = s.get(f"/api/seller/products/{p['id']}").json()["config"]["sizes"]
    assert [x["id"] for x in got] == ["11oz", "15oz"] and got[0]["label"] == "Small" and got[0]["mm"] == 95


def test_publish_and_unpublish(owner):
    s = make_seller(owner)
    p = clone(s)
    assert s.post(f"/api/seller/products/{p['id']}/publish", json={"published": True}).json()["published"] is True
    assert s.post(f"/api/seller/products/{p['id']}/publish", json={"published": False}).json()["published"] is False


def test_published_product_cannot_lose_all_print_areas(owner):
    s = make_seller(owner)
    p = clone(s)
    s.post(f"/api/seller/products/{p['id']}/publish", json={"published": True})
    assert s.put(f"/api/seller/products/{p['id']}", json=edit_body(p, zones=[])).status_code == 422


def test_delete_removes_the_product(owner):
    s = make_seller(owner)
    p = clone(s)
    assert s.delete(f"/api/seller/products/{p['id']}").status_code == 200
    assert s.get(f"/api/seller/products/{p['id']}").status_code == 404


def test_needs_exactly_one_source_and_a_unique_link_name(owner):
    s = make_seller(owner)
    assert s.post("/api/seller/products", json={"name": "n", "slug": "no-source"}).status_code == 422
    assert s.post("/api/seller/products", json={"name": "n", "slug": "two", "template": "custom-printed-mug", "model_id": 1}).status_code == 422
    assert s.post("/api/seller/products", json={"name": "n", "slug": "ok-one", "template": "nope"}).status_code == 404
    clone_ok = s.post("/api/seller/products", json={"name": "n", "slug": "dup-one", "template": "custom-printed-mug"})
    assert clone_ok.status_code == 201
    assert s.post("/api/seller/products", json={"name": "n", "slug": "dup-one", "template": "custom-printed-mug"}).status_code == 409
    assert s.post("/api/seller/products", json={"name": "n", "slug": "Bad Slug!", "template": "custom-printed-mug"}).status_code == 422
