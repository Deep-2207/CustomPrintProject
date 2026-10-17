"""Register, log in, log out, who am I."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import REGISTER_LIMIT_PER_HOUR
from ..database import get_db
from ..deps import COOKIE, csrf, current_user, end_session, start_session
from ..models import AuthSession, Tenant, User
from ..repo import tenant_by_slug
from ..schemas import LoginIn, PasswordIn, RegisterIn
from ..security import burn_time, hash_password, hash_token, limiter, password_problem, verify_password
from ..validation import slug_problem, slugify

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(csrf)])


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def me_payload(user: User) -> dict:
    t = user.tenant
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "tenant": {"id": t.id, "slug": t.slug, "name": t.name, "status": t.status} if t else None}


def _unique_slug(db: Session, base: str) -> str:
    slug, n = base, 1
    while tenant_by_slug(db, slug) is not None or slug_problem(slug):
        n += 1
        slug = f"{base[:36]}-{n}"
    return slug


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    problem = password_problem(body.password, email)
    if problem:                                   # a typo is not an attack: it does not count towards the limit
        raise HTTPException(422, {"errors": [problem]})
    if not limiter.allow(f"register:{_ip(request)}", REGISTER_LIMIT_PER_HOUR, 3600):
        raise HTTPException(429, "Too many sign-ups from this connection. Please try again later.")
    if db.scalar(select(User).where(User.email == email)):
        # Say so plainly: the person is trying to create an account for their own email address.
        raise HTTPException(409, "An account with this email already exists. Try logging in.")
    if body.slug:
        if slug_problem(body.slug):
            raise HTTPException(422, {"errors": [slug_problem(body.slug)]})
        if tenant_by_slug(db, body.slug):
            raise HTTPException(409, "That shop link name is taken. Please choose another.")
        slug = body.slug
    else:
        slug = _unique_slug(db, slugify(body.business))
    tenant = Tenant(slug=slug, name=body.business.strip(), status="pending")
    user = User(tenant=tenant, email=email, name=body.name.strip(), password_hash=hash_password(body.password), role="seller_admin")
    db.add_all([tenant, user])
    db.commit()
    start_session(db, response, user)
    return me_payload(user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    # Limit guessing per connection and per account.
    if not limiter.allow(f"login-ip:{_ip(request)}", 30, 900) or not limiter.allow(f"login-email:{email}", 10, 900):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.active:
        burn_time()                                   # same time as a real check, so timing reveals nothing
        raise HTTPException(401, "Wrong email or password.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    start_session(db, response, user)
    return me_payload(user)


@router.post("/password")
def change_password(body: PasswordIn, request: Request, user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    """Change your own password. Every other login session of this account is ended."""
    if user is None:
        raise HTTPException(401, "Please log in")
    if not limiter.allow(f"pw-change:{user.id}", 10, 900):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    if not verify_password(body.current, user.password_hash):
        raise HTTPException(403, "Your current password is not correct.")
    problem = password_problem(body.new, user.email)
    if problem:
        raise HTTPException(422, {"errors": [problem]})
    user.password_hash = hash_password(body.new)
    keep = hash_token(request.cookies.get(COOKIE, ""))
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != keep))
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    end_session(db, request, response)
    return {"ok": True}


@router.get("/me")
def me(user: User | None = Depends(current_user)):
    return me_payload(user) if user else None
