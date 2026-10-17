"""Product customizer platform API (FastAPI + SQLAlchemy).

Run:  uvicorn app.main:app --reload      (from the platform/ folder)
See README.md for the settings (environment variables).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import ADMIN_KEY, BASE, COOKIE_SECURE, DESIGNS, MODELS, OWNER_EMAIL, OWNER_PASSWORD, UPLOADS
from .database import SessionLocal, get_db
from .models import Product, User
from .routers import auth, embed, owner, public, seller, seller_ops, v1
from .security import hash_password, password_problem
from .seeds import SEEDS


def migrate() -> None:
    """Brings the database up to date (creates the tables on first run)."""
    cfg = Config(str(BASE / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE / "migrations"))
    command.upgrade(cfg, "head")


def seed_products() -> None:
    """Built-in products: insert if missing, replace when their seed_version is newer. Sellers' copies are never touched."""
    with SessionLocal() as db:
        for s in SEEDS:
            row = db.scalar(select(Product).where(Product.tenant_id.is_(None), Product.slug == s["slug"]))
            if row is None:
                db.add(Product(tenant_id=None, slug=s["slug"], name=s["name"], config=s, published=True))
            elif (row.config or {}).get("seed_version", 0) < s["seed_version"]:
                row.name, row.config = s["name"], s
        db.commit()


def bootstrap_owner() -> None:
    """Creates the platform owner from OWNER_EMAIL / OWNER_PASSWORD when no owner exists yet."""
    if not (OWNER_EMAIL and OWNER_PASSWORD):
        return
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.role == "owner")):
            return
        problem = password_problem(OWNER_PASSWORD, OWNER_EMAIL)
        if problem:
            raise SystemExit(f"OWNER_PASSWORD rejected: {problem}")
        db.add(User(tenant_id=None, email=OWNER_EMAIL, name="Owner", password_hash=hash_password(OWNER_PASSWORD), role="owner"))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if COOKIE_SECURE and ADMIN_KEY == "change-me":
        raise SystemExit("Refusing to start: set ADMIN_KEY to a long random value when COOKIE_SECURE=1 (a live site).")
    migrate()
    seed_products()
    bootstrap_owner()
    yield


app = FastAPI(title="Customizer Platform", lifespan=lifespan)

# What a page may load. Scripts only from this site (no inline scripts), so injected markup cannot run code.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "connect-src 'self' data: blob:; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["Referrer-Policy"] = "strict-origin-when-cross-origin"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    if COOKIE_SECURE:
        h["Strict-Transport-Security"] = "max-age=31536000"
    framing = h.get("content-security-policy")          # the embed page names the websites that may frame it
    if framing:
        h["Content-Security-Policy"] = f"{framing}; {CSP}"
    else:
        h["Content-Security-Policy"] = f"{CSP}; frame-ancestors 'self'"
        h["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.get("/healthz", include_in_schema=False)
def healthz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"ok": False}, status_code=503)
    return {"ok": True}


app.include_router(auth.router)
app.include_router(seller.router)
app.include_router(seller_ops.router)
app.include_router(owner.router)
app.include_router(v1.router)
app.include_router(embed.router)
app.include_router(public.router)

# Mount only the public subfolders, never DATA itself (it may hold the database and logs).
for _n, _d in (("models", MODELS), ("uploads", UPLOADS), ("designs", DESIGNS)):
    app.mount(f"/files/{_n}", StaticFiles(directory=_d), name=f"files-{_n}")

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
