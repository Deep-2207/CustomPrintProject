"""Saving a design: shared by the share link, the embed and the API."""
from __future__ import annotations

import base64
import os
import re
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import DESIGNS, MAX_PREVIEW_BYTES
from .models import Design, Product
from .repo import public_config
from .schemas import DesignIn
from .security import limiter
from .usage import bump
from .validation import clean_text, validate_design


# A public key is visible in a web page, so anyone could script saves and run up a seller's bill.
# This caps the designs one shop can receive per hour, whoever sends them. Raise it for a very busy shop.
TENANT_DESIGNS_PER_HOUR = int(os.environ.get("TENANT_DESIGNS_PER_HOUR", "600"))


def store_design(db: Session, d: DesignIn, product: Product, source: str, billable: bool) -> dict:
    """Validates and stores a design. A billable design counts towards the seller's monthly usage."""
    clean = validate_design(public_config(product), d)
    if billable and product.tenant_id is not None and not limiter.allow(f"tenant-designs:{product.tenant_id}", TENANT_DESIGNS_PER_HOUR, 3600):
        raise HTTPException(429, "This shop is receiving a very large number of designs. Please try again in a little while.")
    did = uuid.uuid4().hex[:12]
    if d.preview_png:
        m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", d.preview_png)
        if m:
            raw = base64.b64decode(m.group(1))
            if len(raw) <= MAX_PREVIEW_BYTES and raw[:8] == b"\x89PNG\r\n\x1a\n":
                (DESIGNS / f"{did}.png").write_bytes(raw)
    saved = {"slug": d.slug, "seller": d.seller, "size": d.size, "body_color": d.body_color, "imprint_color": d.imprint_color, "layers": clean}
    ref = re.sub(r"[^\w .#/:@-]", "", clean_text(d.ref or "", 80))[:80]
    billable = billable and product.tenant_id is not None
    db.add(Design(id=did, tenant_id=product.tenant_id, product_id=product.id, product_slug=product.slug, design=saved,
                  source=source, ref=ref, billable=billable))
    db.commit()
    if billable:
        bump(db, product.tenant_id, "design")
    return {"id": did, "preview": f"/files/designs/{did}.png"}


def text_summary(design: dict) -> str:
    """The words a customer typed, on one line (for lists and search)."""
    return " / ".join(l["text"].replace("\n", " ") for l in design.get("layers", []) if l.get("type") == "text")
