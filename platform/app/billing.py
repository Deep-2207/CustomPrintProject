"""Plan maths: what a shop owes for a month. Amounts are whole rupees."""
from __future__ import annotations

import csv
import io

from .config import GST_PERCENT, PLANS
from .models import Tenant


def plan_of(t: Tenant) -> dict:
    return PLANS.get(t.plan) or PLANS["pilot"]


def invoice(t: Tenant, usage: dict | None) -> dict:
    """The invoice for one month. Only designs saved by customers are charged; views and exports are for information."""
    p, u = plan_of(t), usage or {}
    designs = int(u.get("design", 0))
    extra = max(0, designs - p["included"])
    extra_amount = extra * p["overage"]
    setup = 0 if t.setup_fee_paid else int(t.setup_fee or 0)
    subtotal = p["monthly"] + extra_amount + setup
    gst = round(subtotal * GST_PERCENT / 100)
    return {"plan": t.plan, "plan_label": p["label"], "monthly_fee": p["monthly"], "included": p["included"], "designs": designs,
            "extra_designs": extra, "overage_rate": p["overage"], "extra_amount": extra_amount, "setup_fee": setup,
            "subtotal": subtotal, "gst_percent": GST_PERCENT, "gst": gst, "total": subtotal + gst,
            "views": int(u.get("view", 0)), "exports": int(u.get("export", 0))}


COLUMNS = ["shop", "shop_link", "month", "plan", "monthly_fee", "designs", "included", "extra_designs", "overage_rate", "extra_amount",
           "setup_fee", "subtotal", "gst_percent", "gst", "total", "views", "exports"]


def csv_text(rows: list[tuple[Tenant, str, dict]]) -> str:
    """rows = [(tenant, 'YYYY-MM', invoice dict)]"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for t, month, inv in rows:
        w.writerow([_safe(t.name), t.slug, month, inv["plan"], inv["monthly_fee"], inv["designs"], inv["included"], inv["extra_designs"],
                    inv["overage_rate"], inv["extra_amount"], inv["setup_fee"], inv["subtotal"], inv["gst_percent"], inv["gst"],
                    inv["total"], inv["views"], inv["exports"]])
    return buf.getvalue()


def _safe(v: str) -> str:
    """A shop name starting with = + - @ would run as a formula when the CSV is opened in Excel."""
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v
