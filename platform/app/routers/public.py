"""What shoppers and visitors use: products, artwork upload, saving designs, the landing-page sign-up, and the pages."""
from __future__ import annotations

import io
import json
import os
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BASE, DATA, MAX_IMAGE_BYTES, MIN_IMAGE_PX, MODELS, MAX_MODEL_BYTES, UPLOADS
from ..database import get_db
from ..designs import store_design
from ..deps import admin_key, current_user
from ..models import Design, Lead, Product, User
from ..repo import not_found, public_config, tenant_by_slug, visible_product
from ..schemas import DesignIn, LeadIn, ProductIn
from ..security import limiter
from ..usage import bump

router = APIRouter()
Image.MAX_IMAGE_PIXELS = 50_000_000      # refuse decompression bombs (a tiny file that unpacks to gigabytes)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- products
@router.get("/api/products")
def platform_products(db: Session = Depends(get_db)):
    rows = db.scalars(select(Product).where(Product.tenant_id.is_(None), Product.published.is_(True)).order_by(Product.id))
    return [{"slug": p.slug, "name": p.name} for p in rows]


@router.get("/api/products/{slug}")
def platform_product_config(slug: str, db: Session = Depends(get_db)):
    return public_config(visible_product(db, None, slug, None))


@router.get("/api/t/{seller}/products")
def seller_public_products(seller: str, db: Session = Depends(get_db), viewer: User | None = Depends(current_user)):
    t = tenant_by_slug(db, seller)
    if t is None:
        raise not_found()
    member = viewer is not None and (viewer.role == "owner" or viewer.tenant_id == t.id)
    if not member and t.status != "active":
        raise not_found()
    q = select(Product).where(Product.tenant_id == t.id).order_by(Product.id)
    return [{"slug": p.slug, "name": p.name} for p in db.scalars(q) if p.published or member]


@router.get("/api/t/{seller}/products/{slug}")
def seller_public_product(seller: str, slug: str, db: Session = Depends(get_db), viewer: User | None = Depends(current_user)):
    p = visible_product(db, seller, slug, viewer)
    if not (viewer is not None and (viewer.role == "owner" or viewer.tenant_id == p.tenant_id)):
        bump(db, p.tenant_id, "view")          # a shopper opened the product (the seller previewing is not counted)
    return public_config(p)


# ---------------------------------------------------------------- shopper artwork
@router.post("/api/uploads")
async def upload_image(request: Request, file: UploadFile = File(...)):
    if not limiter.allow(f"upload:{_ip(request)}", 60, 3600):
        raise HTTPException(429, "Too many uploads. Please try again later.")
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
    if w * h > Image.MAX_IMAGE_PIXELS:
        raise HTTPException(400, "That image has too many pixels. Please resize it to under 50 megapixels.")
    warn = None
    if min(w, h) < MIN_IMAGE_PX:
        warn = f"Low resolution ({w}x{h}px): it may print blurry. Use at least {MIN_IMAGE_PX}px."
    uid = uuid.uuid4().hex
    ext = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}[fmt]
    (UPLOADS / f"{uid}.{ext}").write_bytes(data)   # original kept for production
    return {"id": uid, "url": f"/files/uploads/{uid}.{ext}", "width": w, "height": h, "warning": warn}


# ---------------------------------------------------------------- designs
@router.post("/api/designs")
def save_design(d: DesignIn, request: Request, db: Session = Depends(get_db), viewer: User | None = Depends(current_user)):
    if not limiter.allow(f"design:{_ip(request)}", 60, 600):
        raise HTTPException(429, "Too many saves. Please wait a few minutes.")
    product = visible_product(db, d.seller, d.slug, viewer)
    member = viewer is not None and (viewer.role == "owner" or viewer.tenant_id == product.tenant_id)
    # A seller (or the owner) trying out their own product is a preview: saved, but not charged.
    return store_design(db, d, product, "preview" if member else "share", billable=not member)


@router.get("/api/designs/{did}")
def get_design(did: str, db: Session = Depends(get_db)):
    if not re.fullmatch(r"[0-9a-f]{12}", did):
        raise not_found()
    row = db.get(Design, did)
    if row is None:
        raise not_found()
    d = json.loads(json.dumps(row.design))
    for l in d["layers"]:
        if l["type"] == "image":
            f = next(iter(UPLOADS.glob(l["upload_id"] + ".*")), None)
            l["url"] = f"/files/uploads/{f.name}" if f else None
    return {"id": did, **d, "preview": f"/files/designs/{did}.png"}


# ---------------------------------------------------------------- landing-page sign-up
def _notify(lead: dict) -> None:
    """Tell the owner about a new sign-up: always append to data/outbox.log, and email it if SMTP is configured
    (env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_TO)."""
    with open(DATA / "outbox.log", "a", encoding="utf8") as f:
        f.write(json.dumps(lead, ensure_ascii=False) + "\n")
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


@router.post("/api/leads")
def create_lead(lead: LeadIn, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if lead.company_site:                      # a bot filled the hidden field: pretend it worked
        return {"ok": True}
    if not limiter.allow(f"lead:{_ip(request)}", 5, 3600):
        raise HTTPException(429, "Too many sign-ups from this connection. Please try again later.")
    data = lead.model_dump(exclude={"company_site"})
    db.add(Lead(**data, ip=_ip(request)))
    db.commit()
    tasks.add_task(_notify, data)
    return {"ok": True}


@router.get("/api/leads", dependencies=[Depends(admin_key)])
def list_leads(db: Session = Depends(get_db)):
    rows = db.scalars(select(Lead).order_by(Lead.id.desc()).limit(500))
    return [{"id": r.id, "created": r.created_at.isoformat(), "business": r.business, "name": r.name, "phone": r.phone,
             "email": r.email, "sells": r.sells, "website": r.website, "city": r.city} for r in rows]


# ---------------------------------------------------------------- legacy admin page (platform products, shared admin key)
@router.put("/api/products/{slug}", dependencies=[Depends(admin_key)])
def put_platform_product(slug: str, p: ProductIn, db: Session = Depends(get_db)):
    if p.slug != slug:
        raise HTTPException(400, "Slug mismatch")
    row = db.scalar(select(Product).where(Product.tenant_id.is_(None), Product.slug == slug))
    cfg = p.model_dump()
    if row is None:
        db.add(Product(tenant_id=None, slug=slug, name=p.name, config=cfg, published=True))
    else:
        row.name, row.config = p.name, cfg
    db.commit()
    return {"ok": True}


@router.delete("/api/products/{slug}", dependencies=[Depends(admin_key)])
def delete_platform_product(slug: str, db: Session = Depends(get_db)):
    row = db.scalar(select(Product).where(Product.tenant_id.is_(None), Product.slug == slug))
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.post("/api/models", dependencies=[Depends(admin_key)])
async def upload_platform_model(file: UploadFile = File(...)):
    data = await file.read(MAX_MODEL_BYTES + 1)
    if len(data) > MAX_MODEL_BYTES:
        raise HTTPException(413, "Model too large (max 25MB). Reduce the polygon count and the texture sizes.")
    if data[:4] != b"glTF":
        raise HTTPException(400, "Only binary glTF (.glb) files are accepted")
    name = f"{uuid.uuid4().hex}.glb"
    (MODELS / name).write_bytes(data)
    return {"url": f"/files/models/{name}", "bytes": len(data)}


# ---------------------------------------------------------------- pages
@router.get("/s/{seller}/{slug}")
def share_page(seller: str, slug: str, db: Session = Depends(get_db), viewer: User | None = Depends(current_user)):
    """A seller's shareable link: /s/<seller>/<product>."""
    if not re.fullmatch(r"[a-z0-9-]{1,40}", seller) or not re.fullmatch(r"[a-z0-9-]{2,60}", slug):
        raise not_found()
    visible_product(db, seller, slug, viewer)     # 404 unless the shopper (or the seller previewing) may see it
    return FileResponse(BASE / "static" / "share.html")


@router.get("/")
def home(request: Request):
    """The landing page, or the customizer when the address names a product or a saved design."""
    q = request.query_params
    return FileResponse(BASE / "static" / ("product.html" if ("product" in q or "design" in q) else "landing.html"))
