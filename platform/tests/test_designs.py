"""Shopper designs and the landing-page sign-up (behaviour that existed before accounts, kept working)."""
import base64
import io

from conftest import new_client


def design(**over):
    return {"slug": "custom-printed-mug", "size": "11oz", "body_color": "#f4f4f4", "layers": []} | over


def text(**over):
    return {"zone": "front", "type": "text", "text": "Deep\nPatel", "font": "Arial", "template": "bubble", "x": .5, "y": .5, "size": .5} | over


def test_save_and_reload_a_design(client):
    r = client.post("/api/designs", json=design(layers=[text(), {"zone": "front", "type": "sticker", "sticker": "star", "x": .1, "y": .2, "scale": .2}]))
    assert r.status_code == 200, r.text
    d = client.get(f"/api/designs/{r.json()['id']}").json()
    assert d["layers"][0]["text"] == "Deep\nPatel" and d["layers"][0]["template"] == "bubble" and d["layers"][1]["sticker"] == "star"


def test_limits_are_enforced_on_the_server(client):
    def errs(layer):
        r = client.post("/api/designs", json=design(layers=[layer]))
        assert r.status_code == 422, r.text
        return " ".join(r.json()["detail"]["errors"])
    assert "characters" in errs(text(text="x" * 61))
    assert "lines" in errs(text(text="a\nb\nc\nd\ne"))
    assert "font" in errs(text(font="Comic Sans"))
    assert "style" in errs(text(template="evil"))
    assert "sticker" in errs({"zone": "front", "type": "sticker", "sticker": "nope"})
    assert "zone" in errs(text(zone="nowhere"))
    assert "number" in errs(text(x="abc"))


def test_line_breaks_are_free_but_letters_count(client):
    ok = text(text="\n".join(["a" * 15] * 4))                 # 60 letters over 4 lines
    assert client.post("/api/designs", json=design(layers=[ok])).status_code == 200


def test_markup_in_text_is_stripped(client):
    r = client.post("/api/designs", json=design(layers=[text(text="<b>Hi</b>{x}`")]))
    assert r.status_code == 200
    assert client.get(f"/api/designs/{r.json()['id']}").json()["layers"][0]["text"] == "bHi/bx"


def test_unknown_product_and_bad_colour(client):
    assert client.post("/api/designs", json=design(slug="no-such")).status_code == 404
    assert client.post("/api/designs", json=design(body_color="red")).status_code == 400
    assert client.post("/api/designs", json=design(size="99oz")).status_code == 400


def test_design_ids_cannot_be_guessed_into_other_files(client):
    for bad in ("../etc/passwd", "zzzzzzzzzzzz", "123", "000000000000"):
        assert client.get(f"/api/designs/{bad}").status_code == 404


def test_preview_png_is_validated(client):
    png = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (4, 4), "red").save(png, "PNG")
    good = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode()
    r = client.post("/api/designs", json=design(preview_png=good))
    assert r.status_code == 200 and client.get(r.json()["preview"]).status_code == 200
    fake = "data:image/png;base64," + base64.b64encode(b"<html>not a png</html>").decode()
    r2 = client.post("/api/designs", json=design(preview_png=fake))
    assert r2.status_code == 200 and client.get(r2.json()["preview"]).status_code == 404     # saved without a picture


def test_artwork_upload_checks(client):
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGBA", (400, 400), "blue").save(buf, "PNG")
    r = client.post("/api/uploads", files={"file": ("logo.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["warning"] is None
    small = io.BytesIO(); Image.new("RGB", (50, 50), "red").save(small, "PNG")
    assert "Low resolution" in client.post("/api/uploads", files={"file": ("s.png", small.getvalue(), "image/png")}).json()["warning"]
    assert client.post("/api/uploads", files={"file": ("x.png", b"<svg onload=alert(1)>", "image/png")}).status_code == 400
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
    assert client.post("/api/uploads", files={"file": ("x.svg", svg, "image/svg+xml")}).status_code == 400


def test_an_uploaded_logo_can_be_used_in_a_design(client):
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGBA", (400, 400), "blue").save(buf, "PNG")
    up = client.post("/api/uploads", files={"file": ("logo.png", buf.getvalue(), "image/png")}).json()
    layer = {"zone": "front", "type": "image", "upload_id": up["id"], "x": .5, "y": .5, "scale": .5}
    assert client.post("/api/designs", json=design(layers=[layer])).status_code == 200
    layer["upload_id"] = "0" * 32
    assert client.post("/api/designs", json=design(layers=[layer])).status_code == 422


# ---------------------------------------------------------------- landing-page sign-ups
LEAD = {"business": "Test Gifts", "name": "Asha", "phone": "+91 98765 43210", "email": "a@b.in"}


def test_signup_is_stored_and_listed_for_the_owner(client, owner):
    assert client.post("/api/leads", json=LEAD | {"business": "Lead One"}).json() == {"ok": True}
    assert "Lead One" in {l["business"] for l in owner.get("/api/owner/leads").json()}


def test_signup_rejects_bad_phone_and_email(client):
    assert client.post("/api/leads", json=LEAD | {"phone": "abc"}).status_code == 422
    assert client.post("/api/leads", json=LEAD | {"email": "nope"}).status_code == 422


def test_signup_spam_trap_and_rate_limit(client, owner):
    assert client.post("/api/leads", json=LEAD | {"business": "Bot Shop", "company_site": "spam"}).json() == {"ok": True}
    assert "Bot Shop" not in {l["business"] for l in owner.get("/api/owner/leads").json()}
    codes = [client.post("/api/leads", json=LEAD).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_legacy_admin_key_endpoints(client):
    assert client.get("/api/leads").status_code == 401
    assert client.get("/api/leads", headers={"x-admin-key": "wrong"}).status_code == 401
    assert client.get("/api/leads", headers={"x-admin-key": "change-me"}).status_code == 200
    assert client.put("/api/products/custom-printed-mug", json={}).status_code in (401, 422)
