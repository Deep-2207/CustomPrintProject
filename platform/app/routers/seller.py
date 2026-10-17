"""Everything a seller does in their dashboard. Every query is filtered by the logged-in seller's tenant_id."""
from __future__ import annotations

import copy
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_MODEL_BYTES, MODELS
from ..database import get_db
from ..deps import csrf, require_seller, require_seller_admin
from ..glb import inspect_glb
from ..models import ModelFile, Product, User
from ..repo import model_for_product, public_config, seller_model, seller_product, seller_products
from ..schemas import NewProductIn, PublishIn, SellerProductEdit
from ..validation import TEMPLATE_MESHES, clean_text, merge_seller_edit

router = APIRouter(prefix="/api/seller", tags=["seller"], dependencies=[Depends(csrf)])

MAX_PRODUCTS, MAX_MODELS = 25, 15

STARTER_COLORS = [{"name": n, "hex": h} for n, h in [("White", "#f4f4f4"), ("Black", "#1b1b1b"), ("Red", "#d62828"), ("Blue", "#1d6fe8")]]
STARTER_IMPRINTS = [{"name": n, "hex": h} for n, h in [("Auto", ""), ("Black", "#111111"), ("White", "#ffffff"), ("Gold", "#d4a017")]]


def _summary(p: Product) -> dict:
    m = p.config.get("model") or {}
    return {"id": p.id, "slug": p.slug, "name": p.name, "published": p.published, "zones": len(p.config.get("zones", [])),
            "model": m.get("template") or m.get("type"), "updated_at": p.updated_at.isoformat() if p.updated_at else None}


def _meshes_for(db: Session, p: Product) -> set[str] | None:
    """The part names a print area may refer to, or None when they cannot be checked."""
    m = p.config.get("model") or {}
    if m.get("type") == "template":
        return TEMPLATE_MESHES.get(m.get("template"))
    mf = model_for_product(db, p)
    if mf is None:
        return set()
    return {x["three_name"] for x in mf.report.get("meshes", [])} | set(mf.report.get("nodes", []))


@router.get("/templates")
def templates(user: User = Depends(require_seller), db: Session = Depends(get_db)):
    rows = db.scalars(select(Product).where(Product.tenant_id.is_(None), Product.published.is_(True)).order_by(Product.id))
    return [{"slug": p.slug, "name": p.name, "template": (p.config.get("model") or {}).get("template")} for p in rows]


@router.get("/products")
def list_products(user: User = Depends(require_seller), db: Session = Depends(get_db)):
    return [_summary(p) for p in seller_products(db, user.tenant_id)]


@router.post("/products", status_code=201)
def create_product(body: NewProductIn, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    if bool(body.template) == bool(body.model_id):
        raise HTTPException(422, {"errors": ["Choose either a template or an uploaded 3D model."]})
    if db.scalar(select(func.count()).select_from(Product).where(Product.tenant_id == user.tenant_id)) >= MAX_PRODUCTS:
        raise HTTPException(422, {"errors": [f"You can have up to {MAX_PRODUCTS} products."]})
    if db.scalar(select(Product.id).where(Product.tenant_id == user.tenant_id, Product.slug == body.slug)):
        raise HTTPException(409, "You already have a product with that link name. Choose another.")
    name = clean_text(body.name, 120)
    if not name:
        raise HTTPException(422, {"errors": ["Give the product a name."]})

    if body.template:
        src = db.scalar(select(Product).where(Product.tenant_id.is_(None), Product.slug == body.template, Product.published.is_(True)))
        if src is None:
            raise HTTPException(404, "Template not found")
        cfg = copy.deepcopy(src.config)
        cfg.pop("seed_version", None)
        cfg["clone_of"] = src.slug
    else:
        mf = seller_model(db, user.tenant_id, body.model_id)
        if not mf.report.get("valid"):
            raise HTTPException(422, {"errors": ["That 3D model has problems and cannot be used."]})
        cfg = {"model": {"type": "glb", "url": f"/files/models/{mf.filename}"}, "sizes": [], "colors": STARTER_COLORS,
               "imprint_colors": STARTER_IMPRINTS, "fonts": ["Arial", "Impact"], "zones": [], "body_meshes": [], "price": {"base": 0, "currency": "INR"},
               "defaults": {"bodyColor": STARTER_COLORS[0]["hex"], "tpl": "plain", "textSize": 0.45}, "sample": "Your\nName",
               "placeholder": "Type your message", "demos": []}
    cfg["slug"], cfg["name"] = body.slug, name
    p = Product(tenant_id=user.tenant_id, slug=body.slug, name=name, config=cfg, published=False)
    db.add(p)
    db.commit()
    return {**_summary(p), "config": public_config(p)}


@router.get("/products/{product_id}")
def get_product(product_id: int, user: User = Depends(require_seller), db: Session = Depends(get_db)):
    p = seller_product(db, user.tenant_id, product_id)
    mf = model_for_product(db, p)
    return {**_summary(p), "config": public_config(p), "tenant_slug": user.tenant.slug,
            "model_report": mf.report if mf else None, "model_name": mf.original_name if mf else None}


@router.put("/products/{product_id}")
def edit_product(product_id: int, body: SellerProductEdit, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    p = seller_product(db, user.tenant_id, product_id)
    cfg = merge_seller_edit(p.config, body, _meshes_for(db, p))
    if p.published and not cfg["zones"]:
        raise HTTPException(422, {"errors": ["A published product needs at least one print area. Unpublish it first."]})
    p.config, p.name = cfg, cfg["name"]
    db.commit()
    return {**_summary(p), "config": public_config(p)}


@router.post("/products/{product_id}/publish")
def publish(product_id: int, body: PublishIn, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    p = seller_product(db, user.tenant_id, product_id)
    if body.published and not p.config.get("zones"):
        raise HTTPException(422, {"errors": ["Add at least one print area before publishing."]})
    p.published = body.published
    db.commit()
    return _summary(p)


@router.delete("/products/{product_id}")
def delete_product(product_id: int, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    db.delete(seller_product(db, user.tenant_id, product_id))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 3D models
@router.get("/models")
def list_models(user: User = Depends(require_seller), db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelFile).where(ModelFile.tenant_id == user.tenant_id).order_by(ModelFile.id.desc()))
    return [{"id": m.id, "url": f"/files/models/{m.filename}", "name": m.original_name, "bytes": m.size_bytes, "report": m.report} for m in rows]


@router.post("/models", status_code=201)
async def upload_model(file: UploadFile = File(...), user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    if db.scalar(select(func.count()).select_from(ModelFile).where(ModelFile.tenant_id == user.tenant_id)) >= MAX_MODELS:
        raise HTTPException(422, {"errors": [f"You can keep up to {MAX_MODELS} models. Delete one first."]})
    data = await file.read(MAX_MODEL_BYTES + 1)
    if len(data) > MAX_MODEL_BYTES:
        raise HTTPException(413, "Model too large (max 25MB). Reduce the polygon count and the texture sizes.")
    report = inspect_glb(data)
    if not report["valid"]:
        raise HTTPException(422, {"errors": report["errors"], "report": report})
    name = f"{uuid.uuid4().hex}.glb"
    (MODELS / name).write_bytes(data)
    original = re.sub(r"[^A-Za-z0-9._ -]", "", (file.filename or "model.glb"))[:120] or "model.glb"
    mf = ModelFile(tenant_id=user.tenant_id, filename=name, original_name=original, size_bytes=len(data), report=report)
    db.add(mf)
    db.commit()
    return {"id": mf.id, "url": f"/files/models/{name}", "name": original, "bytes": len(data), "report": report}
