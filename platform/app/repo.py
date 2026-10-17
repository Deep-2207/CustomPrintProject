"""Database lookups. Anything a seller can reach goes through here and is filtered by tenant_id,
so one seller can never read or change another seller's data."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Design, ModelFile, Product, Tenant, User


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(404, what)


def tenant_by_slug(db: Session, slug: str) -> Tenant | None:
    return db.scalar(select(Tenant).where(Tenant.slug == slug))


def platform_product(db: Session, slug: str) -> Product | None:
    return db.scalar(select(Product).where(Product.tenant_id.is_(None), Product.slug == slug, Product.published.is_(True)))


def seller_products(db: Session, tenant_id: int) -> list[Product]:
    return list(db.scalars(select(Product).where(Product.tenant_id == tenant_id).order_by(Product.id)))


def seller_product(db: Session, tenant_id: int, product_id: int) -> Product:
    """A product of this seller, or 404. A product id belonging to another seller is also 404, so ids leak nothing."""
    p = db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id))
    if p is None:
        raise not_found("Product not found")
    return p


def seller_model(db: Session, tenant_id: int, model_id: int) -> ModelFile:
    m = db.scalar(select(ModelFile).where(ModelFile.id == model_id, ModelFile.tenant_id == tenant_id))
    if m is None:
        raise not_found("Model not found")
    return m


def seller_design(db: Session, tenant_id: int, design_id: str) -> Design:
    """A design saved on this seller's products, or 404 (another seller's design id answers 404 too)."""
    d = db.scalar(select(Design).where(Design.id == design_id, Design.tenant_id == tenant_id))
    if d is None:
        raise not_found("Design not found")
    return d


def model_for_product(db: Session, p: Product) -> ModelFile | None:
    """The uploaded model a seller product uses, if any."""
    url = (p.config.get("model") or {}).get("url") or ""
    name = url.rsplit("/", 1)[-1]
    if p.tenant_id is None or not name:
        return None
    return db.scalar(select(ModelFile).where(ModelFile.tenant_id == p.tenant_id, ModelFile.filename == name))


def visible_product(db: Session, seller_slug: str | None, slug: str, viewer: User | None) -> Product:
    """The product a shopper (or the seller previewing) may see, or 404.

    Platform demo products are public. A seller's product is public only when it is published and the
    seller is active; the seller's own team (and the platform owner) can always preview it.
    """
    if not seller_slug:
        p = platform_product(db, slug)
        if p is None:
            raise not_found("Product not found")
        return p
    t = tenant_by_slug(db, seller_slug)
    if t is None:
        raise not_found("Product not found")
    p = db.scalar(select(Product).where(Product.tenant_id == t.id, Product.slug == slug))
    if p is None:
        raise not_found("Product not found")
    member = viewer is not None and (viewer.role == "owner" or viewer.tenant_id == t.id)
    if not member and not (t.status == "active" and p.published):
        raise not_found("Product not found")
    return p


def public_config(p: Product) -> dict:
    """What the browser receives: the stored config with the authoritative columns laid over it."""
    return {**p.config, "slug": p.slug, "name": p.name, "published": p.published}
