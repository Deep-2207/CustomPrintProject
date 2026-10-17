"""Small admin commands. Run from the platform folder:

    python -m app.manage create-owner you@example.com     asks for a password; makes the platform owner login
    python -m app.manage demo-shop                        makes an approved demo shop "ahmedabad-gifts" with the mug and wristband published
    python -m app.manage pilot-shop "Shop name" a@b.com   makes an approved pilot shop (free plan) and prints its first password
    python -m app.manage reset-password a@b.com           asks for a new password for any account (a seller who forgot theirs)
"""
from __future__ import annotations

import copy
import getpass
import secrets
import sys

from sqlalchemy import select

from .database import SessionLocal
from .main import migrate, seed_products
from .models import AuthSession, Product, Tenant, User
from .security import hash_password, password_problem
from .validation import slugify

DEMO_SLUG = "ahmedabad-gifts"
DEMO_EMAIL = "demo@previewprint.local"


def create_owner(email: str) -> None:
    email = email.strip().lower()
    migrate()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit(f"{email} already has an account.")
        pw = getpass.getpass("Password (at least 10 characters): ")
        if pw != getpass.getpass("Again: "):
            sys.exit("The passwords do not match.")
        problem = password_problem(pw, email)
        if problem:
            sys.exit(problem)
        db.add(User(tenant_id=None, email=email, name="Owner", password_hash=hash_password(pw), role="owner"))
        db.commit()
    print(f"Owner account created for {email}. Log in at /account.html")


def demo_shop() -> None:
    migrate()
    seed_products()
    with SessionLocal() as db:
        t = db.scalar(select(Tenant).where(Tenant.slug == DEMO_SLUG))
        if t is None:
            t = Tenant(slug=DEMO_SLUG, name="Ahmedabad Gifts (demo)", status="active")
            db.add(t)
            db.flush()
        if not db.scalar(select(User).where(User.email == DEMO_EMAIL)):
            pw = secrets.token_urlsafe(12)
            db.add(User(tenant_id=t.id, email=DEMO_EMAIL, name="Demo Seller", password_hash=hash_password(pw), role="seller_admin"))
            print(f"Demo seller login: {DEMO_EMAIL}   password: {pw}   (shown once)")
        for src in db.scalars(select(Product).where(Product.tenant_id.is_(None))):
            if db.scalar(select(Product.id).where(Product.tenant_id == t.id, Product.slug == src.slug)):
                continue
            cfg = copy.deepcopy(src.config)
            cfg.pop("seed_version", None)
            cfg["clone_of"] = src.slug
            db.add(Product(tenant_id=t.id, slug=src.slug, name=src.name, config=cfg, published=True))
        db.commit()
    print(f"Demo shop ready. Try /s/{DEMO_SLUG}/custom-printed-mug")


def pilot_shop(business: str, email: str) -> None:
    """A done-for-you start: an approved shop on the free pilot plan, with the built-in products copied in as drafts."""
    email = email.strip().lower()
    migrate()
    seed_products()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit(f"{email} already has an account.")
        base, slug, n = slugify(business) or "shop", None, 1
        slug = base
        while db.scalar(select(Tenant).where(Tenant.slug == slug)):
            n += 1
            slug = f"{base[:36]}-{n}"
        pw = secrets.token_urlsafe(12)
        t = Tenant(slug=slug, name=business.strip(), status="active", plan="pilot")
        db.add(t)
        db.flush()
        db.add(User(tenant_id=t.id, email=email, name=business.strip()[:80], password_hash=hash_password(pw), role="seller_admin"))
        for src in db.scalars(select(Product).where(Product.tenant_id.is_(None))):
            cfg = copy.deepcopy(src.config)
            cfg.pop("seed_version", None)
            cfg["clone_of"] = src.slug
            db.add(Product(tenant_id=t.id, slug=src.slug, name=src.name, config=cfg, published=False))
        db.commit()
    print(f"Pilot shop '{business}' ready (link name: {slug}).")
    print(f"Login: {email}   password: {pw}   (shown once; ask them to change it under Account)")
    print(f"Their products are drafts. They publish them, then share /s/{slug}/<product>.")


def reset_password(email: str) -> None:
    email = email.strip().lower()
    migrate()
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        if u is None:
            sys.exit(f"No account for {email}.")
        pw = getpass.getpass("New password (at least 10 characters): ")
        if pw != getpass.getpass("Again: "):
            sys.exit("The passwords do not match.")
        problem = password_problem(pw, email)
        if problem:
            sys.exit(problem)
        u.password_hash = hash_password(pw)
        for sess in db.scalars(select(AuthSession).where(AuthSession.user_id == u.id)):
            db.delete(sess)                                  # log out every device
        db.commit()
    print(f"Password changed for {email}. All their logins were ended.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create-owner" and len(sys.argv) == 3:
        create_owner(sys.argv[2])
    elif cmd == "demo-shop":
        demo_shop()
    elif cmd == "pilot-shop" and len(sys.argv) == 4:
        pilot_shop(sys.argv[2], sys.argv[3])
    elif cmd == "reset-password" and len(sys.argv) == 3:
        reset_password(sys.argv[2])
    else:
        sys.exit(__doc__)
