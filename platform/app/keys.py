"""API keys and the list of websites allowed to embed the customizer."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApiKey, Tenant
from .security import hash_token, new_token

MAX_SECRET_KEYS, MAX_DOMAINS = 3, 10
_HOST = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(:[0-9]{2,5})?$|^(localhost|127\.0\.0\.1)(:[0-9]{2,5})?$")


def normalise_domain(raw: str) -> str:
    """'https://Shop.Example.com/page' -> 'shop.example.com'. Accepts host, host:port and *.host. Raises ValueError otherwise."""
    d = raw.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d).split("/")[0].split("?")[0].split("#")[0]
    if not _HOST.match(d):
        raise ValueError(f"'{raw.strip()[:60]}' is not a valid website address. Use something like shop.example.com.")
    return d


def clean_domains(items: list[str]) -> list[str]:
    out: list[str] = []
    for raw in items:
        if raw.strip():
            d = normalise_domain(raw)
            if d not in out:
                out.append(d)
    if len(out) > MAX_DOMAINS:
        raise ValueError(f"You can list up to {MAX_DOMAINS} websites.")
    return out


def origins_for(domains: list[str]) -> list[str]:
    """Web origins (scheme + host) a browser may frame the customizer from."""
    out: list[str] = []
    for d in domains:
        local = d.split(":")[0] in ("localhost", "127.0.0.1")
        out += [f"http://{d}", f"https://{d}"] if local else [f"https://{d}"]
    return out


def origin_allowed(domains: list[str], origin: str) -> bool:
    """Is this page origin (e.g. https://shop.example.com) on the list? *.example.com matches one subdomain level, not the bare domain."""
    o = origin.strip().lower().rstrip("/")
    if o in origins_for(domains):
        return True
    if o.startswith("https://"):
        host = o[len("https://"):]
        for d in domains:
            if d.startswith("*.") and host.endswith(d[1:]):
                sub = host[: -len(d[1:])]
                if sub and "." not in sub:
                    return True
    return False


def frame_ancestors(domains: list[str]) -> str:
    """The Content-Security-Policy value that makes browsers refuse to show the customizer on any other site."""
    srcs = " ".join(origins_for(domains))
    return f"frame-ancestors 'self' {srcs}".strip()


def public_key(db: Session, tenant: Tenant) -> str:
    """The shop's public key (it appears in the embed snippet and is not secret). Created on first use."""
    k = db.scalar(select(ApiKey).where(ApiKey.tenant_id == tenant.id, ApiKey.kind == "public", ApiKey.revoked_at.is_(None)))
    if k is None:
        value = "pk_" + new_token()[:24]
        k = ApiKey(tenant_id=tenant.id, kind="public", prefix=value[:10], key_value=value)
        db.add(k)
        db.commit()
    return k.key_value


def rotate_public_key(db: Session, tenant: Tenant) -> str:
    for k in db.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant.id, ApiKey.kind == "public", ApiKey.revoked_at.is_(None))):
        k.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return public_key(db, tenant)


def create_secret(db: Session, tenant: Tenant) -> tuple[ApiKey, str]:
    live = db.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant.id, ApiKey.kind == "secret", ApiKey.revoked_at.is_(None))).all()
    if len(live) >= MAX_SECRET_KEYS:
        raise HTTPException(422, {"errors": [f"You can have up to {MAX_SECRET_KEYS} secret keys. Revoke one first."]})
    raw = "sk_" + new_token()
    k = ApiKey(tenant_id=tenant.id, kind="secret", prefix=raw[:10], key_value=hash_token(raw))
    db.add(k)
    db.commit()
    return k, raw


def tenant_for_public_key(db: Session, key: str) -> Tenant | None:
    if not re.fullmatch(r"pk_[A-Za-z0-9_-]{10,40}", key):
        return None
    k = db.scalar(select(ApiKey).where(ApiKey.key_value == key, ApiKey.kind == "public", ApiKey.revoked_at.is_(None)))
    return db.get(Tenant, k.tenant_id) if k else None


def tenant_for_secret_key(db: Session, raw: str) -> Tenant | None:
    if not re.fullmatch(r"sk_[A-Za-z0-9_-]{20,80}", raw):
        return None
    k = db.scalar(select(ApiKey).where(ApiKey.key_value == hash_token(raw), ApiKey.kind == "secret", ApiKey.revoked_at.is_(None)))
    if k is None:
        return None
    k.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return db.get(Tenant, k.tenant_id)


def describe(k: ApiKey) -> dict:
    return {"id": k.id, "kind": k.kind, "prefix": k.prefix, "created_at": k.created_at.isoformat(),
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None}
