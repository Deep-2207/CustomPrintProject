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
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
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
        c.execute("""CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT DEFAULT CURRENT_TIMESTAMP,
                     business TEXT, name TEXT, phone TEXT, email TEXT, sells TEXT, website TEXT, city TEXT, ip TEXT)""")
        # Built-in products: insert if missing; replace when the built-in definition has a newer seed_version.
        # (Admin edits to a built-in product are replaced on a version bump; use a new slug for your own variants.)
        for p in SEEDS:
            row = c.execute("SELECT config FROM products WHERE slug=?", (p["slug"],)).fetchone()
            if row is None or json.loads(row["config"]).get("seed_version", 0) < p["seed_version"]:
                c.execute("INSERT OR REPLACE INTO products VALUES(?,?)", (p["slug"], json.dumps(p)))


SEED: dict[str, Any] = {
    "slug": "custom-embossed-wristband",
    "name": "Custom Embossed Wristbands",
    "model": {"type": "template", "template": "band", "url": None},
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
    # What a fresh customizer starts with, the hint text, and ready-made examples for demos.
    "defaults": {"bodyColor": "#1fb5e8", "tpl": "plain", "textSize": 0.45},
    "sample": "TEAM 2026",
    "placeholder": "e.g. TEAM SPIRIT 2026",
    "demos": [
        {"name": "Team spirit", "body_color": "#1d6fe8", "zones": {"front": {"text": "TEAM SPIRIT 2026"}, "back": {"text": "NEVER GIVE UP"}}},
        {"name": "Charity run", "body_color": "#d62828", "imprint_color": "#ffffff", "zones": {"front": {"text": "RUN FOR LIFE"}, "back": {"text": "5K - AHMEDABAD"}}},
        {"name": "Event pass", "body_color": "#1b1b1b", "imprint_color": "#d4a017", "zones": {"front": {"text": "VIP ACCESS"}, "back": {"text": "ALL NIGHT LONG"}}},
    ],
}


MUG_SEED: dict[str, Any] = {
    "slug": "custom-printed-mug",
    "name": "Custom Printed Mugs",
    "model": {"type": "template", "template": "mug", "url": None},
    # height / radius in millimetres drive the 3D shape (see static/js/templates.js)
    "sizes": [{"id": "11oz", "label": "11 oz (325 ml)", "mm": 95, "radius": 41}, {"id": "15oz", "label": "15 oz (440 ml)", "mm": 110, "radius": 44}],
    "colors": [{"name": n, "hex": h} for n, h in [("White", "#f4f4f4"), ("Black", "#1b1b1b"), ("Red", "#d62828"), ("Blue", "#1d6fe8"),
                                                  ("Green", "#2a9d3f"), ("Yellow", "#facc15"), ("Orange", "#f97316"), ("Pink", "#ec4899")]],
    "imprint_colors": [{"name": n, "hex": h} for n, h in [("Auto", ""), ("Black", "#111111"), ("White", "#ffffff"), ("Gold", "#d4a017"), ("Red", "#d62828")]],
    "fonts": ["Arial", "Impact", "Georgia", "Courier New", "Trebuchet MS"],
    # Two fixed print rectangles, one each side of the handle. With the handle on the viewer's left the
    # visible side is the FRONT; turn the mug and the BACK area faces you. y0/y1 = top/bottom of the area.
    "zones": [
        {"id": "front", "label": "Front print area", "mesh": "mug_outer", "style": "print", "max_chars": 60, "max_lines": 4, "allow_images": True,
         "u0": 0.09, "u1": 0.41, "y0": 0.14, "y1": 0.86, "guide": True},
        {"id": "back", "label": "Back print area", "mesh": "mug_outer", "style": "print", "max_chars": 60, "max_lines": 4, "allow_images": True,
         "u0": 0.59, "u1": 0.91, "y0": 0.14, "y1": 0.86, "guide": True},
    ],
    "body_meshes": ["mug_outer"],
    "price": {"base": 250.0, "currency": "INR"},
    "defaults": {"bodyColor": "#f4f4f4", "tpl": "bubble", "textSize": 0.6},
    "sample": "Your\nName",
    "placeholder": "Type a name or message. Press Enter for a new line",
    "demos": [
        {"name": "World's best dad", "body_color": "#f4f4f4",
         "zones": {"front": {"text": "WORLD'S\nBEST\nDAD", "tpl": "bubble"}, "back": {"text": "Since\n1985", "tpl": "script"}}},
        {"name": "Name gift", "body_color": "#1b1b1b",
         "zones": {"front": {"text": "Deep\nPatel", "tpl": "script", "color": "#ffd166",
                             "stickers": [{"id": "star", "x": 0.14, "y": 0.18, "scale": 0.16}, {"id": "star", "x": 0.86, "y": 0.82, "scale": 0.16}]}}},
        {"name": "Team mug", "body_color": "#1d6fe8",
         "zones": {"front": {"text": "TEAM\nAHMEDABAD", "tpl": "badge"}, "back": {"text": "Work hard\nDrink chai", "tpl": "shadow"}}},
        {"name": "Mr & Mrs", "body_color": "#ec4899",
         "zones": {"front": {"text": "Mr &\nMrs Patel", "tpl": "shadow",
                             "stickers": [{"id": "heart", "x": 0.12, "y": 0.2, "scale": 0.18}, {"id": "heart", "x": 0.88, "y": 0.8, "scale": 0.18}]}}},
    ],
}

SEED_VERSION = 2   # bump when a built-in product definition above changes
SEEDS = [SEED, MUG_SEED]
for _p in SEEDS:
    _p["seed_version"] = SEED_VERSION


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
    allow_stickers: bool = True
    max_lines: int = Field(default=1, ge=1, le=10)   # how many text lines the area accepts
    u0: float = 0.0
    u1: float = 1.0
    aspect: float = 0.0          # width/height of the whole UV surface of the mesh (0 = auto)
    y0: float = Field(default=0.0, ge=0, le=1)   # top of the printable rectangle (fraction of the surface height)
    y1: float = Field(default=1.0, ge=0, le=1)   # bottom of the printable rectangle
    guide: bool = False          # draw a dashed outline of the area on the preview


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
    defaults: dict = {}            # starting colour, text style and text size
    sample: str = ""               # text shown in the style previews while the customer has typed nothing
    placeholder: str = ""          # hint inside the empty message box
    demos: list[dict] = []         # ready-made examples for the demo bar
    seed_version: int = 0          # set on built-in products only


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
CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f<>`\\{}]")   # strips control chars but keeps newline
MAX_STICKERS_PER_ZONE = 10
# Sticker ids come from static/stickers.json, the single source of truth shared with the browser.
STICKER_IDS = {s["id"] for s in json.loads((BASE / "static" / "stickers.json").read_text(encoding="utf8"))}
TEXT_STYLE_IDS = {s["id"] for s in json.loads((BASE / "static" / "text-styles.json").read_text(encoding="utf8"))}


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
            raw = str(l.get("text", "")).replace("\r\n", "\n").replace("\r", "\n")
            text = CONTROL.sub("", raw)[:1000].strip()
            chars = len(text.replace("\n", ""))           # line breaks are free; letters count
            lines = text.count("\n") + 1 if text else 0
            if chars > z["max_chars"]:
                errors.append(f"{z['label']}: {chars} characters, limit is {z['max_chars']}")
                continue
            if lines > z.get("max_lines", 1):
                errors.append(f"{z['label']}: {lines} lines, limit is {z.get('max_lines', 1)}")
                continue
            if l.get("font") not in prod["fonts"]:
                errors.append(f"{z['label']}: font not allowed")
                continue
            tpl = l.get("template") or "plain"
            if tpl not in TEXT_STYLE_IDS:
                errors.append(f"{z['label']}: unknown text style")
                continue
            clean.append({**{k: l[k] for k in ("zone", "type", "font") }, "template": tpl, "text": text,
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
        elif l.get("type") == "sticker":
            if not z.get("allow_stickers", True):
                errors.append(f"{z['label']}: stickers are not allowed here")
                continue
            if l.get("sticker") not in STICKER_IDS:
                errors.append(f"{z['label']}: unknown sticker")
                continue
            if sum(1 for c in clean if c["zone"] == l["zone"] and c["type"] == "sticker") >= MAX_STICKERS_PER_ZONE:
                errors.append(f"{z['label']}: at most {MAX_STICKERS_PER_ZONE} stickers")
                continue
            clean.append({"zone": l["zone"], "type": "sticker", "sticker": l["sticker"], "x": float(l.get("x", .5)), "y": float(l.get("y", .5)),
                          "scale": float(l.get("scale", .35)), "rot": float(l.get("rot", 0))})
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


# ---------- sign-ups (leads) from the landing page ----------
LEAD_LIMIT, LEAD_WINDOW = 5, 3600          # at most 5 sign-ups per IP per hour
_lead_hits: dict[str, list[float]] = {}


class LeadIn(BaseModel):
    business: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(pattern=r"^\+?[0-9 \-]{7,18}$")
    email: str = Field(default="", max_length=120, pattern=r"^([^@\s]+@[^@\s]+\.[^@\s]+)?$")
    sells: str = Field(default="", max_length=300)
    website: str = Field(default="", max_length=200)
    city: str = Field(default="Ahmedabad", max_length=60)
    company_site: str = ""        # honeypot: real visitors never see or fill this field


def _notify(lead: dict) -> None:
    """Tell the owner about a new sign-up: always append to data/outbox.log, and email it if SMTP is configured
    (env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_TO)."""
    line = json.dumps(lead, ensure_ascii=False)
    with open(DATA / "outbox.log", "a", encoding="utf8") as f:
        f.write(line + "\n")
    host, to = os.environ.get("SMTP_HOST"), os.environ.get("NOTIFY_TO")
    if not (host and to):
        return
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = f"New seller sign-up: {lead['business']}"
        msg["From"] = os.environ.get("SMTP_USER", to)
        msg["To"] = to
        msg.set_content("\n".join(f"{k}: {v}" for k, v in lead.items()))
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
    except Exception as e:   # never fail the sign-up because email failed
        with open(DATA / "outbox.log", "a", encoding="utf8") as f:
            f.write(json.dumps({"email_error": str(e)}) + "\n")


@app.post("/api/leads")
def create_lead(lead: LeadIn, request: Request, tasks: BackgroundTasks):
    if lead.company_site:                      # a bot filled the hidden field: pretend it worked
        return {"ok": True}
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = [t for t in _lead_hits.get(ip, []) if now - t < LEAD_WINDOW]
    if len(hits) >= LEAD_LIMIT:
        raise HTTPException(429, "Too many sign-ups from this connection. Please try again later.")
    _lead_hits[ip] = hits + [now]
    data = lead.model_dump(exclude={"company_site"})
    with db() as c:
        c.execute("INSERT INTO leads(business,name,phone,email,sells,website,city,ip) VALUES(?,?,?,?,?,?,?,?)",
                  (data["business"], data["name"], data["phone"], data["email"], data["sells"], data["website"], data["city"], ip))
    tasks.add_task(_notify, data)
    return {"ok": True}


@app.get("/api/leads", dependencies=[Depends(admin)])
def list_leads():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id,created,business,name,phone,email,sells,website,city FROM leads ORDER BY id DESC LIMIT 500")]


# ---------- static ----------
# Mount only the public subfolders — never DATA itself (it holds the SQLite DB).
for _n, _d in (("models", MODELS), ("uploads", UPLOADS), ("designs", DESIGNS)):
    app.mount(f"/files/{_n}", StaticFiles(directory=_d), name=f"files-{_n}")


@app.get("/s/{seller}/{slug}")
def share_page(seller: str, slug: str):
    """Shareable link page: /s/<seller>/<product>. Sellers become real accounts in week 3."""
    if not re.fullmatch(r"[a-z0-9-]{1,40}", seller) or not re.fullmatch(r"[a-z0-9-]{2,60}", slug):
        raise HTTPException(404, "Not found")
    _product(slug)   # 404 if the product does not exist
    return FileResponse(BASE / "static" / "share.html")


@app.get("/")
def home(request: Request):
    """The landing page, or the customizer when the address names a product or a saved design."""
    q = request.query_params
    return FileResponse(BASE / "static" / ("product.html" if ("product" in q or "design" in q) else "landing.html"))


app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
