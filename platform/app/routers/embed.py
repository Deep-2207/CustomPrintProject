"""The embeddable customizer: the page a seller puts in an iframe, and the calls that page makes.

A seller's public key (pk_...) names the shop. Which websites may show the page is enforced by the browser:
the page is served with a Content-Security-Policy `frame-ancestors` header listing the seller's allowed websites.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import BASE
from ..database import get_db
from ..deps import current_user
from ..designs import store_design
from ..keys import frame_ancestors, origin_allowed, tenant_for_public_key
from ..models import Product, Tenant, User
from ..repo import not_found, public_config
from ..schemas import DesignIn
from ..security import limiter
from ..usage import bump

router = APIRouter()

NOT_AVAILABLE = ("<!doctype html><meta charset=utf-8><title>Not available</title>"
                 "<p style='font:16px sans-serif;padding:24px'>This product is not available. Please contact the shop.</p>")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _shop(db: Session, key: str) -> Tenant:
    t = tenant_for_public_key(db, key)
    if t is None or t.status != "active":
        raise not_found()
    return t


def _product(db: Session, t: Tenant, slug: str) -> Product:
    p = db.scalar(select(Product).where(Product.tenant_id == t.id, Product.slug == slug, Product.published.is_(True)))
    if p is None:
        raise not_found("Product not found")
    return p


@router.get("/embed/{key}/{slug}")
def embed_page(key: str, slug: str, db: Session = Depends(get_db)):
    """The customizer for use inside an iframe on the seller's own website."""
    t = tenant_for_public_key(db, key)
    ok = t is not None and t.status == "active" and re.fullmatch(r"[a-z0-9-]{2,60}", slug) and \
        db.scalar(select(Product.id).where(Product.tenant_id == t.id, Product.slug == slug, Product.published.is_(True)))
    if not ok:
        return HTMLResponse(NOT_AVAILABLE, status_code=404, headers={"Content-Security-Policy": "frame-ancestors 'self'"})
    return FileResponse(BASE / "static" / "share.html", headers={"Content-Security-Policy": frame_ancestors(t.allowed_domains or []),
                                                                "Cache-Control": "no-store"})


@router.get("/api/embed/{key}/products/{slug}")
def embed_product(key: str, slug: str, db: Session = Depends(get_db)):
    t = _shop(db, key)
    p = _product(db, t, slug)
    bump(db, t.id, "view")
    return public_config(p)


@router.get("/api/embed/{key}/host")
def embed_host(key: str, origin: str = "", db: Session = Depends(get_db)):
    """Is this website on the seller's list? The embedded page only posts messages to a website that is."""
    t = _shop(db, key)
    return {"allowed": bool(origin) and origin_allowed(t.allowed_domains or [], origin)}


@router.post("/api/embed/{key}/designs")
def embed_save(key: str, d: DesignIn, request: Request, db: Session = Depends(get_db), viewer: User | None = Depends(current_user)):
    if request.headers.get("x-requested-with") != "fetch":
        raise HTTPException(403, "Missing request header")
    if not limiter.allow(f"design:{_ip(request)}", 60, 600):
        raise HTTPException(429, "Too many saves. Please wait a few minutes.")
    t = _shop(db, key)
    p = _product(db, t, d.slug)
    member = viewer is not None and (viewer.role == "owner" or viewer.tenant_id == t.id)
    d.seller = t.slug
    return store_design(db, d, p, "preview" if member else "embed", billable=not member)
