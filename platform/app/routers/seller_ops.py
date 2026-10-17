"""Seller dashboard, part 2: embed settings and keys, the designs list, usage and the invoice.
Same rules as seller.py: every query is filtered by the logged-in seller's tenant_id."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import billing, keys, usage
from ..config import PLANS, UPLOADS
from ..database import get_db
from ..deps import csrf, require_active_seller, require_seller, require_seller_admin
from ..designs import text_summary
from ..models import ApiKey, Design, Product, User
from ..repo import public_config, seller_design, seller_products
from ..schemas import DomainsIn, KeyIn

router = APIRouter(prefix="/api/seller", tags=["seller"], dependencies=[Depends(csrf)])


# ---------------------------------------------------------------- embed settings: public key, allowed websites, secret keys
def _settings(db: Session, user: User) -> dict:
    t = user.tenant
    live = db.scalars(select(ApiKey).where(ApiKey.tenant_id == t.id, ApiKey.kind == "secret", ApiKey.revoked_at.is_(None)).order_by(ApiKey.id))
    return {"public_key": keys.public_key(db, t), "allowed_domains": t.allowed_domains or [], "shop": t.slug,
            "secret_keys": [keys.describe(k) for k in live], "max_secret_keys": keys.MAX_SECRET_KEYS}


@router.get("/settings")
def get_settings(user: User = Depends(require_seller), db: Session = Depends(get_db)):
    return _settings(db, user)


@router.put("/settings/domains")
def set_domains(body: DomainsIn, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    try:
        user.tenant.allowed_domains = keys.clean_domains(body.domains)
    except ValueError as e:
        raise HTTPException(422, {"errors": [str(e)]})
    db.commit()
    return _settings(db, user)


@router.post("/keys", status_code=201)
def create_key(body: KeyIn, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    """secret: the key is shown once, here, and never again. public: replaces the public key (embeds using the old one stop working)."""
    if body.kind == "public":
        keys.rotate_public_key(db, user.tenant)
        return _settings(db, user)
    _, raw = keys.create_secret(db, user.tenant)
    return {**_settings(db, user), "new_secret": raw}


@router.delete("/keys/{key_id}")
def revoke_key(key_id: int, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    k = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == user.tenant_id, ApiKey.kind == "secret", ApiKey.revoked_at.is_(None)))
    if k is None:
        raise HTTPException(404, "Key not found")
    k.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return _settings(db, user)


# ---------------------------------------------------------------- designs customers saved
def _design_row(d: Design, names: dict[int, str]) -> dict:
    layers = d.design.get("layers", [])
    return {"id": d.id, "product_id": d.product_id, "product": names.get(d.product_id) or d.product_slug, "product_slug": d.product_slug,
            "created_at": d.created_at.isoformat(), "source": d.source, "ref": d.ref, "billable": d.billable,
            "text": text_summary(d.design), "stickers": sum(1 for l in layers if l.get("type") == "sticker"),
            "images": sum(1 for l in layers if l.get("type") == "image"), "preview": f"/files/designs/{d.id}.png"}


@router.get("/designs")
def list_designs(q: str = "", product_id: int | None = None, page: int = 1, user: User = Depends(require_seller), db: Session = Depends(get_db)):
    """Newest first, 20 per page. `q` searches the design id, your order reference, the product and the words customers typed."""
    stmt = select(Design).where(Design.tenant_id == user.tenant_id).order_by(Design.created_at.desc(), Design.id.desc())
    if product_id is not None:
        stmt = stmt.where(Design.product_id == product_id)
    names = {p.id: p.name for p in seller_products(db, user.tenant_id)}
    needle = q.strip().lower()[:80]
    rows = []
    for d in db.scalars(stmt.limit(2000)):          # the newest 2000 are searched; plenty for a pilot
        r = _design_row(d, names)
        if needle and needle not in f"{r['id']} {r['ref']} {r['text']} {r['product']}".lower():
            continue
        rows.append(r)
    page = max(1, page)
    return {"total": len(rows), "page": page, "per_page": 20, "designs": rows[(page - 1) * 20: page * 20]}


@router.get("/designs/{design_id}")
def design_detail(design_id: str, user: User = Depends(require_seller), db: Session = Depends(get_db)):
    """The full design plus its product, for the print-file page."""
    d = seller_design(db, user.tenant_id, design_id)
    p = db.get(Product, d.product_id) if d.product_id else None
    saved = json.loads(json.dumps(d.design))
    for l in saved.get("layers", []):
        if l.get("type") == "image":
            f = next(iter(UPLOADS.glob(l["upload_id"] + ".*")), None)
            l["url"] = f"/files/uploads/{f.name}" if f else None
    return {**_design_row(d, {p.id: p.name} if p else {}), "design": saved, "product_config": public_config(p) if p else None}


@router.post("/designs/{design_id}/exported")
def design_exported(design_id: str, user: User = Depends(require_active_seller), db: Session = Depends(get_db)):
    """The print page calls this when the seller downloads print files (shown on the usage page)."""
    seller_design(db, user.tenant_id, design_id)
    usage.bump(db, user.tenant_id, "export")
    return {"ok": True}


# ---------------------------------------------------------------- usage, plan and invoice
def check_month(month: str | None) -> str | None:
    if month is not None and not re.fullmatch(r"20[0-9]{2}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, {"errors": ["Month must look like 2026-10."]})
    return month


@router.get("/usage")
def get_usage(month: str | None = None, user: User = Depends(require_seller), db: Session = Depends(get_db)):
    u = usage.per_day(db, user.tenant_id, check_month(month))
    return {**u, "plan": {**PLANS.get(user.tenant.plan, PLANS["pilot"]), "id": user.tenant.plan},
            "invoice": billing.invoice(user.tenant, u["totals"])}


@router.get("/invoice.csv")
def my_invoice(month: str | None = None, user: User = Depends(require_seller_admin), db: Session = Depends(get_db)):
    u = usage.per_day(db, user.tenant_id, check_month(month))
    body = billing.csv_text([(user.tenant, u["month"], billing.invoice(user.tenant, u["totals"]))])
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="usage-{u["month"]}.csv"'})
