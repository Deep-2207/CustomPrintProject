"""Product customizer platform API (FastAPI + SQLite).

Run:  uvicorn app.main:app --reload      (from the platform/ folder)
Env:  ADMIN_KEY   secret for admin endpoints (default 'change-me' — set it in production)
      DATA_DIR    where SQLite + uploads live (default ./data)
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA_DIR", BASE / "data"))
MODELS, UPLOADS, DESIGNS = DATA / "models", DATA / "uploads", DATA / "designs"
for d in (MODELS, UPLOADS, DESIGNS):
    d.mkdir(parents=True, exist_ok=True)
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")

MAX_MODEL_BYTES = 25 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_PX = 300          # shorter side; smaller artwork prints blurry
MAX_PREVIEW_BYTES = 3 * 1024 * 1024

app = FastAPI(title="Customizer Platform")


# ---------- storage ----------
def db() -> sqlite3.Connection:
    con = sqlite3.connect(DATA / "platform.db")
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS products(slug TEXT PRIMARY KEY, config TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS designs(id TEXT PRIMARY KEY, slug TEXT, design TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP)")
        if not c.execute("SELECT 1 FROM products LIMIT 1").fetchone():
            c.execute("INSERT INTO products VALUES(?,?)", ("custom-embossed-wristband", json.dumps(SEED)))


SEED: dict[str, Any] = {
    "slug": "custom-embossed-wristband",
    "name": "Custom Embossed Wristbands",
    "model": {"type": "procedural-band", "url": None},
    "sizes": [{"id": "1/2", "label": '1/2"', "mm": 12.7}, {"id": "3/4", "label": '3/4"', "mm": 19}, {"id": "1", "label": '1"', "mm": 25.4}],
    "colors": [{"name": n, "hex": h} for n, h in [("Blue", "#1d6fe8"), ("Cyan", "#1fb5e8"), ("Black", "#1b1b1b"), ("Red", "#d62828"),
                                                  ("Green", "#2a9d3f"), ("Yellow", "#facc15"), ("Orange", "#f97316"), ("Purple", "#7e3ff2"), ("White", "#f4f4f4")]],
    "imprint_colors": [{"name": n, "hex": h} for n, h in [("None", ""), ("White", "#ffffff"), ("Black", "#111111"), ("Gold", "#d4a017"), ("Silver", "#c0c6cc")]],
    "fonts": ["Arial", "Impact", "Georgia", "Courier New", "Trebuchet MS"],
    "zones": [
        {"id": "front", "label": "Front message", "mesh": "band_outer", "style": "emboss", "max_chars": 28, "allow_images": True, "u0": 0.0, "u1": 0.5},
        {"id": "back", "label": "Back message", "mesh": "band_outer", "style": "emboss", "max_chars": 28, "allow_images": True, "u0": 0.5, "u1": 1.0},
    ],
    "body_meshes": ["band_outer"],
    "price": {"base": 16.0, "currency": "INR"},
}


@app.on_event("startup")
def _startup() -> None:
    init_db()


# ---------- auth ----------
def admin(x_admin_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(401, "Admin key required")


# ---------- schemas ----------
class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    label: str = Field(max_length=60)
    mesh: str = Field(max_length=80)
    style: str = Field(default="print", pattern=r"^(emboss|deboss|print)$")
    max_chars: int = Field(default=28, ge=1, le=500)
    allow_images: bool = True
    u0: float = 0.0
    u1: float = 1.0
    aspect: float = 0.0          # width/height of the whole UV surface of the mesh (0 = auto)


class ProductIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,60}$")
    name: str = Field(max_length=120)
    model: dict
    sizes: list[dict] = []
    colors: list[dict] = []
    imprint_colors: list[dict] = []
    fonts: list[str] = ["Arial"]
    zones: list[Zone]
    body_meshes: list[str] = []
    price: dict = {}


# ---------- products ----------
def _product(slug: str) -> dict:
    with db() as c:
        r = c.execute("SELECT config FROM products WHERE slug=?", (slug,)).fetchone()
    if not r:
        raise HTTPException(404, "Product not found")
    return json.loads(r["config"])


@app.get("/api/products")
def list_products():
    with db() as c:
        return [{"slug": r["slug"], "name": json.loads(r["config"])["name"]} for r in c.execute("SELECT * FROM products")]


@app.get("/api/products/{slug}")
def get_product(slug: str):
    return _product(slug)


@app.put("/api/products/{slug}", dependencies=[Depends(admin)])
def put_product(slug: str, p: ProductIn):
    if p.slug != slug:
        raise HTTPException(400, "Slug mismatch")
    with db() as c:
        c.execute("INSERT OR REPLACE INTO products VALUES(?,?)", (slug, p.model_dump_json()))
    return {"ok": True}


@app.delete("/api/products/{slug}", dependencies=[Depends(admin)])
def del_product(slug: str):
    with db() as c:
        c.execute("DELETE FROM products WHERE slug=?", (slug,))
    return {"ok": True}


# ---------- 3D model upload (admin) ----------
@app.post("/api/models", dependencies=[Depends(admin)])
async def upload_model(file: UploadFile = File(...)):
    data = await file.read(MAX_MODEL_BYTES + 1)
    if len(data) > MAX_MODEL_BYTES:
        raise HTTPException(413, "Model too large (max 25MB). Compress it with gltf-transform / Draco.")
    if data[:4] != b"glTF":
        raise HTTPException(400, "Only binary glTF (.glb) files are accepted")
    name = f"{uuid.uuid4().hex}.glb"
    (MODELS / name).write_bytes(data)
    return {"url": f"/files/models/{name}", "bytes": len(data)}


# ---------- customer artwork upload ----------
@app.post("/api/uploads")
async def upload_image(file: UploadFile = File(...)):
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 10MB)")
    try:
        im = Image.open(io.BytesIO(data))
        im.verify()
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "").upper()
    except Exception:
        raise HTTPException(400, "Not a valid image")
    if fmt not in ("PNG", "JPEG", "WEBP", "GIF"):
        raise HTTPException(400, "Use PNG, JPG, WEBP or GIF")
    w, h = im.size
    warn = None
    if min(w, h) < MIN_IMAGE_PX:
        warn = f"Low resolution ({w}x{h}px): it may print blurry. Use at least {MIN_IMAGE_PX}px."
    uid = uuid.uuid4().hex
    ext = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}[fmt]
    (UPLOADS / f"{uid}.{ext}").write_bytes(data)   # original kept for production
    return {"id": uid, "url": f"/files/uploads/{uid}.{ext}", "width": w, "height": h, "warning": warn}


# ---------- designs ----------
CONTROL = re.compile(r"[\x00-\x1f\x7f<>`\\{}]")


class DesignIn(BaseModel):
    slug: str
    size: str | None = None
    body_color: str = "#1d6fe8"
    imprint_color: str = ""
    layers: list[dict] = Field(max_length=60)
    preview_png: str | None = None   # data URL of the rendered 3D view


@app.post("/api/designs")
def save_design(d: DesignIn):
    prod = _product(d.slug)
    zones = {z["id"]: z for z in prod["zones"]}
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", d.body_color) or (d.imprint_color and not re.fullmatch(r"#[0-9a-fA-F]{6}", d.imprint_color)):
        raise HTTPException(400, "Invalid colour")
    if d.size and d.size not in [s["id"] for s in prod["sizes"]]:
        raise HTTPException(400, "Invalid size")
    errors, clean = [], []
    for i, l in enumerate(d.layers):
        z = zones.get(l.get("zone"))
        if not z:
            errors.append(f"Layer {i + 1}: unknown zone")
            continue
        if l.get("type") == "text":
            text = CONTROL.sub("", str(l.get("text", "")))[:1000].strip()
            if len(text) > z["max_chars"]:
                errors.append(f"{z['label']}: {len(text)} characters, limit is {z['max_chars']}")
                continue
            if l.get("font") not in prod["fonts"]:
                errors.append(f"{z['label']}: font not allowed")
                continue
            clean.append({**{k: l[k] for k in ("zone", "type", "font") }, "text": text,
                          "color": l.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", str(l.get("color", ""))) else "",
                          "x": float(l.get("x", .5)), "y": float(l.get("y", .5)), "size": float(l.get("size", .5)), "rot": float(l.get("rot", 0))})
        elif l.get("type") == "image":
            if not z["allow_images"]:
                errors.append(f"{z['label']}: images are not allowed here")
                continue
            uid = str(l.get("upload_id", ""))
            if not re.fullmatch(r"[0-9a-f]{32}", uid) or not list(UPLOADS.glob(uid + ".*")):
                errors.append(f"{z['label']}: image not found, upload it again")
                continue
            clean.append({"zone": l["zone"], "type": "image", "upload_id": uid, "x": float(l.get("x", .5)), "y": float(l.get("y", .5)),
                          "scale": float(l.get("scale", .5)), "rot": float(l.get("rot", 0))})
        else:
            errors.append(f"Layer {i + 1}: unknown type")
    if errors:
        raise HTTPException(422, {"errors": errors})
    did = uuid.uuid4().hex[:12]
    if d.preview_png:
        m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", d.preview_png)
        if m:
            raw = base64.b64decode(m.group(1))
            if len(raw) <= MAX_PREVIEW_BYTES and raw[:8] == b"\x89PNG\r\n\x1a\n":
                (DESIGNS / f"{did}.png").write_bytes(raw)
    saved = {"slug": d.slug, "size": d.size, "body_color": d.body_color, "imprint_color": d.imprint_color, "layers": clean}
    with db() as c:
        c.execute("INSERT INTO designs(id,slug,design) VALUES(?,?,?)", (did, d.slug, json.dumps(saved)))
    return {"id": did, "preview": f"/files/designs/{did}.png"}


@app.get("/api/designs/{did}")
def get_design(did: str):
    if not re.fullmatch(r"[0-9a-f]{12}", did):
        raise HTTPException(404, "Not found")
    with db() as c:
        r = c.execute("SELECT design FROM designs WHERE id=?", (did,)).fetchone()
    if not r:
        raise HTTPException(404, "Not found")
    d = json.loads(r["design"])
    for l in d["layers"]:
        if l["type"] == "image":
            f = next(iter(UPLOADS.glob(l["upload_id"] + ".*")), None)
            l["url"] = f"/files/uploads/{f.name}" if f else None
    return {"id": did, **d, "preview": f"/files/designs/{did}.png"}


# ---------- static ----------
# Mount only the public subfolders — never DATA itself (it holds the SQLite DB).
for _n, _d in (("models", MODELS), ("uploads", UPLOADS), ("designs", DESIGNS)):
    app.mount(f"/files/{_n}", StaticFiles(directory=_d), name=f"files-{_n}")


@app.get("/")
def home():
    return FileResponse(BASE / "static" / "product.html")


app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
