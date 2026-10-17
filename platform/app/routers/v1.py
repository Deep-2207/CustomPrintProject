"""Public API for a seller's own server. Authenticated with a secret key:  Authorization: Bearer sk_...

Every call is limited to the shop that owns the key.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..designs import text_summary
from ..keys import tenant_for_secret_key
from ..models import Design, Product, Tenant
from ..repo import not_found
from ..security import limiter

router = APIRouter(prefix="/api/v1", tags=["api"])


def shop(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)) -> Tenant:
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    t = tenant_for_secret_key(db, token) if token else None
    if t is None or t.status != "active":
        if not limiter.allow(f"badkey:{request.client.host if request.client else '?'}", 30, 600):   # each failure counts: guessing keys is slowed down
            raise HTTPException(429, "Too many failed attempts")
        raise HTTPException(401, "Invalid or missing API key")
    if not limiter.allow(f"v1:{t.id}", 120, 60):
        raise HTTPException(429, "Rate limit: 120 requests per minute")
    return t


def _row(d: Design, base: str, shop_slug: str, full: bool = False) -> dict:
    out = {"id": d.id, "product": d.product_slug, "created_at": d.created_at.isoformat(), "source": d.source, "ref": d.ref,
           "text": text_summary(d.design), "preview_url": f"{base}/files/designs/{d.id}.png", "open_url": f"{base}/s/{shop_slug}/{d.product_slug}?design={d.id}"}
    if full:
        out["design"] = d.design
    return out


@router.get("/products")
def products(t: Tenant = Depends(shop), db: Session = Depends(get_db)):
    rows = db.scalars(select(Product).where(Product.tenant_id == t.id, Product.published.is_(True)).order_by(Product.id))
    return [{"slug": p.slug, "name": p.name} for p in rows]


@router.get("/designs")
def designs(request: Request, limit: int = 50, before: str | None = None, ref: str | None = None,
            t: Tenant = Depends(shop), db: Session = Depends(get_db)):
    """Newest first. Pass `before=<design id>` for the next page, or `ref=` to find the designs for one of your orders."""
    q = select(Design).where(Design.tenant_id == t.id).order_by(Design.created_at.desc(), Design.id.desc())
    if ref:
        q = q.where(Design.ref == ref)
    if before:
        cur = db.scalar(select(Design).where(Design.id == before, Design.tenant_id == t.id))
        if cur is None:
            raise not_found("Unknown 'before' design")
        q = q.where(or_(Design.created_at < cur.created_at, and_(Design.created_at == cur.created_at, Design.id < cur.id)))
    base = str(request.base_url).rstrip("/")
    return [_row(d, base, t.slug) for d in db.scalars(q.limit(max(1, min(limit, 100))))]


@router.get("/designs/{design_id}")
def one_design(design_id: str, request: Request, t: Tenant = Depends(shop), db: Session = Depends(get_db)):
    if not re.fullmatch(r"[0-9a-f]{12}", design_id):
        raise not_found("Design not found")
    d = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == t.id))
    if d is None:
        raise not_found("Design not found")
    return _row(d, str(request.base_url).rstrip("/"), t.slug, full=True)
