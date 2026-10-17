"""FastAPI dependencies: who is logged in, and what they may do."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import ADMIN_KEY, COOKIE_SECURE, SESSION_DAYS
from .database import get_db
from .models import AuthSession, User, utcnow
from .security import hash_token, new_token

COOKIE = "sid"


def aware(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def start_session(db: Session, response: Response, user: User) -> None:
    token = new_token()
    db.add(AuthSession(token_hash=hash_token(token), user_id=user.id, expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at < utcnow()))   # tidy up old sessions
    db.commit()
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(COOKIE, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    s = db.get(AuthSession, hash_token(token))
    if s is None or aware(s.expires_at) < datetime.now(timezone.utc):
        return None
    u = db.get(User, s.user_id)
    return u if u is not None and u.active else None


def csrf(request: Request) -> None:
    """Changes made with a login cookie must carry a custom header. A web page on another site cannot add it
    to a request to us (the browser would first ask permission, and we never grant it), so forged requests fail."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("x-requested-with") != "fetch":
        raise HTTPException(403, "Missing request header")


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(401, "Please log in")
    return user


def require_seller(user: User = Depends(require_user)) -> User:
    if user.tenant_id is None:
        raise HTTPException(403, "This area is for sellers")
    return user


def require_active_seller(user: User = Depends(require_seller), db: Session = Depends(get_db)) -> User:
    """Sellers can log in and look around while pending, but changes need an approved account."""
    if user.tenant.status != "active":
        msg = "Your account is waiting for approval." if user.tenant.status == "pending" else "Your account is suspended."
        raise HTTPException(403, msg)
    return user


def require_seller_admin(user: User = Depends(require_active_seller)) -> User:
    if user.role != "seller_admin":
        raise HTTPException(403, "Only the shop admin can do this")
    return user


def require_owner(user: User = Depends(require_user)) -> User:
    if user.role != "owner":
        raise HTTPException(403, "Platform owner only")
    return user


def admin_key(x_admin_key: str = Header(default="")) -> None:
    """Legacy: the shared admin key, still used by the old admin page."""
    if not secrets.compare_digest(x_admin_key.encode(), ADMIN_KEY.encode()):
        raise HTTPException(401, "Admin key required")
