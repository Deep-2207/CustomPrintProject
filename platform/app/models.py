"""Database tables.

Tenant isolation rule: every row a seller can touch carries tenant_id, and every seller query filters by it
(see repo.py). tenant_id NULL means "belongs to the platform" (the built-in template products).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """A seller account."""
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)       # used in the shareable link
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="pending")           # pending | active | suspended
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")            # sites allowed to embed the customizer
    plan: Mapped[str] = mapped_column(String(16), default="pilot", server_default="pilot")   # see config.PLANS
    setup_fee: Mapped[int] = mapped_column(Integer, default=0, server_default="0")           # one-off, INR
    setup_fee_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class ApiKey(Base):
    """public: shown in the embed snippet (not secret). secret: for server-to-server calls; only its hash is stored."""
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))                                 # public | secret
    prefix: Mapped[str] = mapped_column(String(16))                              # first characters, so a seller can recognise a key
    key_value: Mapped[str] = mapped_column(String(64), unique=True)              # the key itself (public) or its SHA-256 (secret)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageDaily(Base):
    """One counter per shop, day (India time) and kind: view | design | export."""
    __tablename__ = "usage_daily"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("tenant_id", "day", "kind", name="uq_usage_day_kind"),)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)  # NULL = platform owner
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)     # stored lower-case
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))                                # owner | seller_admin | seller_staff
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    tenant: Mapped[Tenant | None] = relationship(back_populates="users")


class AuthSession(Base):
    """Server-side login session. Only a hash of the cookie token is stored."""
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON)                                   # sizes, colours, fonts, zones, defaults...
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_product_tenant_slug"),
        # NULL tenants never collide in a plain unique constraint, so platform slugs get their own index.
        Index("uq_platform_product_slug", "slug", unique=True,
              sqlite_where=(tenant_id.is_(None)), postgresql_where=(tenant_id.is_(None))),
    )


class ModelFile(Base):
    """An uploaded 3D model (GLB) and the report from checking it."""
    __tablename__ = "model_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(64), unique=True)               # random name on disk
    original_name: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Design(Base):
    __tablename__ = "designs"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    product_slug: Mapped[str] = mapped_column(String(60))
    design: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(10), default="share", server_default="share")   # share | embed | preview
    ref: Mapped[str] = mapped_column(String(80), default="", server_default="")                 # the seller's own order reference
    billable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    business: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(24))
    email: Mapped[str] = mapped_column(String(120), default="")
    sells: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(60), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
