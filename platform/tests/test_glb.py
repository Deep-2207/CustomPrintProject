"""Days 18 to 20: uploading a 3D model, the report on it, and print areas on its parts."""
import struct
import uuid

from conftest import make_glb, make_seller

from app.glb import inspect_glb


def upload(c, data, name="model.glb"):
    return c.post("/api/seller/models", files={"file": (name, data, "model/gltf-binary")})


def test_report_lists_parts_triangles_and_uv_status():
    rep = inspect_glb(make_glb([("Cup Body", True), ("Handle", False)], triangles=100))
    assert rep["valid"] and rep["total_triangles"] == 200
    assert {m["name"]: (m["triangles"], m["has_uv"]) for m in rep["meshes"]} == {"Cup Body": (100, True), "Handle": (100, False)}
    assert rep["meshes"][0]["three_name"] == "Cup_Body"          # how three.js will name it
    assert any("Handle" in w and "UV" in w for w in rep["warnings"])


def test_no_uv_at_all_is_an_error():
    rep = inspect_glb(make_glb([("Flat", False)]))
    assert not rep["valid"] and any("UV" in e for e in rep["errors"])


def test_heavy_models_get_a_warning():
    rep = inspect_glb(make_glb([("Big", True)], triangles=250_000))
    assert rep["valid"] and any("heavy" in w.lower() for w in rep["warnings"])


def test_damaged_files_are_rejected_not_crashed_on():
    good = make_glb()
    cases = {
        "not a glb": b"hello world, this is not a model",
        "empty": b"",
        "truncated": good[:30],
        "wrong length": good + b"extra",
        "version 1": good[:4] + struct.pack("<I", 1) + good[8:],
        "json is junk": good[:20] + b"{" * (len(good) - 20),
        "json chunk too long": good[:12] + struct.pack("<I", 10**9) + good[16:],
    }
    for label, data in cases.items():
        rep = inspect_glb(data)
        assert rep["valid"] is False and rep["errors"], label


def test_hostile_json_does_not_crash_the_inspector():
    import json
    doc = {"accessors": "nope", "meshes": [None, 5, {"primitives": "x"}, {"name": 7, "primitives": [{"attributes": []}]}], "nodes": [1, {"name": None}]}
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    data = b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body
    rep = inspect_glb(data)            # must return a report, not raise
    assert isinstance(rep["errors"], list)


def test_upload_stores_the_file_and_returns_the_report(owner):
    s = make_seller(owner)
    r = upload(s, make_glb([("Cup", True)]), "My Cup (final).glb")
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["report"]["valid"] and j["url"].startswith("/files/models/") and j["name"] == "My Cup final.glb"
    from conftest import new_client
    assert new_client().get(j["url"]).status_code == 200
    assert [m["id"] for m in s.get("/api/seller/models").json()] == [j["id"]]


def test_bad_uploads_are_refused(owner):
    s = make_seller(owner)
    r = upload(s, b"not a model")
    assert r.status_code == 422 and r.json()["detail"]["errors"]
    r = upload(s, make_glb([("Flat", False)]))
    assert r.status_code == 422 and "UV" in " ".join(r.json()["detail"]["errors"])
    assert s.get("/api/seller/models").json() == []              # nothing was stored


def test_staff_and_pending_sellers_cannot_upload(owner):
    pending = make_seller(owner, approve=False)
    assert upload(pending, make_glb()).status_code == 403


def test_product_from_model_starts_without_print_areas_and_zones_must_match_parts(owner):
    s = make_seller(owner)
    mid = upload(s, make_glb([("Body", True), ("Lid", True), ("Flat", False)])).json()["id"]
    r = s.post("/api/seller/products", json={"name": "Custom thing", "slug": f"t-{uuid.uuid4().hex[:6]}", "model_id": mid})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["config"]["model"]["type"] == "glb" and p["config"]["zones"] == []
    assert s.post(f"/api/seller/products/{p['id']}/publish", json={"published": True}).status_code == 422   # needs a print area first

    def body(mesh):
        c = p["config"]
        z = {"id": "label", "label": "Label", "mesh": mesh, "style": "print", "max_chars": 30, "max_lines": 2, "u0": 0.1, "u1": 0.9, "y0": 0.2, "y1": 0.8, "aspect": 3.0, "guide": True}
        return {"name": c["name"], "sizes": [], "colors": c["colors"], "imprint_colors": c["imprint_colors"], "fonts": c["fonts"], "zones": [z],
                "defaults": c["defaults"], "sample": "", "placeholder": "", "price": {"base": 0}}
    assert s.put(f"/api/seller/products/{p['id']}", json=body("Nonexistent")).status_code == 422
    assert s.put(f"/api/seller/products/{p['id']}", json=body("Flat")).status_code == 200      # exists in the file (warned about, not blocked here)
    assert s.put(f"/api/seller/products/{p['id']}", json=body("Body")).status_code == 200
    assert s.post(f"/api/seller/products/{p['id']}/publish", json={"published": True}).status_code == 200
    got = s.get(f"/api/seller/products/{p['id']}").json()
    assert got["model_report"]["valid"] and got["config"]["zones"][0]["mesh"] == "Body" and got["config"]["body_meshes"] == ["Body"]


def test_part_names_with_spaces_match_the_way_three_js_names_them(owner):
    s = make_seller(owner)
    mid = upload(s, make_glb([("Cup Body", True)])).json()["id"]
    p = s.post("/api/seller/products", json={"name": "Spaced", "slug": f"sp-{uuid.uuid4().hex[:6]}", "model_id": mid}).json()
    c = p["config"]
    z = {"id": "a", "label": "A", "mesh": "Cup_Body", "style": "print", "max_chars": 10, "u0": 0, "u1": 1, "y0": 0, "y1": 1}
    r = s.put(f"/api/seller/products/{p['id']}", json={"name": "Spaced", "colors": c["colors"], "fonts": c["fonts"], "zones": [z], "defaults": c["defaults"]})
    assert r.status_code == 200, r.text


def _glb_with(extra):
    """The tiny test model with extra top-level glTF fields merged in."""
    import json
    import struct
    base = make_glb()
    doc = json.loads(base[20:20 + struct.unpack_from("<I", base, 12)[0]].decode().strip())
    doc.update(extra)
    js = json.dumps(doc).encode()
    js += b" " * (-len(js) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    return b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body


def test_files_outside_the_model_are_refused():
    for extra in ({"images": [{"uri": "https://tracker.example/pixel.png"}]}, {"buffers": [{"uri": "../uploads/secret.bin", "byteLength": 1}]},
                  {"images": [{"uri": "//evil.example/x.png"}]}):
        rep = inspect_glb(_glb_with(extra))
        assert not rep["valid"] and any("outside" in e for e in rep["errors"]), extra


def test_embedded_data_is_allowed():
    rep = inspect_glb(_glb_with({"images": [{"uri": "data:image/png;base64,iVBORw0KGgo="}]}))
    assert rep["valid"], rep["errors"]


def test_models_needing_unsupported_compression_are_refused_with_advice():
    for ext in ("KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_texture_basisu"):
        rep = inspect_glb(_glb_with({"extensionsRequired": [ext]}))
        assert not rep["valid"] and any(ext in e and "compression" in e for e in rep["errors"]), ext
    assert inspect_glb(_glb_with({"extensionsRequired": ["KHR_texture_transform"]}))["valid"]    # harmless extensions are fine
