"""Platform owner screens: approve sellers, see sign-ups."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import billing, usage
from ..config import PLANS
from ..database import get_db
from ..deps import csrf, require_owner
from ..models import Design, Lead, Product, Tenant, User
from ..schemas import PlanIn, StatusIn
from .seller_ops import check_month

router = APIRouter(prefix="/api/owner", tags=["owner"], dependencies=[Depends(csrf), Depends(require_owner)])


@router.get("/tenants")
def tenants(status: str | None = None, month: str | None = None, db: Session = Depends(get_db)):
    q = select(Tenant).order_by(Tenant.id.desc())
    if status:
        q = q.where(Tenant.status == status)
    month = usage.month_bounds(check_month(month))[0].strftime("%Y-%m")
    used = usage.totals_by_tenant(db, month)
    out = []
    for t in db.scalars(q):
        admin = db.scalar(select(User).where(User.tenant_id == t.id, User.role == "seller_admin").order_by(User.id))
        out.append({"id": t.id, "slug": t.slug, "name": t.name, "status": t.status, "created_at": t.created_at.isoformat(),
                    "email": admin.email if admin else "", "owner_name": admin.name if admin else "",
                    "products": db.scalar(select(func.count()).select_from(Product).where(Product.tenant_id == t.id)),
                    "designs": db.scalar(select(func.count()).select_from(Design).where(Design.tenant_id == t.id)),
                    "plan": t.plan, "setup_fee": t.setup_fee, "setup_fee_paid": t.setup_fee_paid, "month": month,
                    "invoice": billing.invoice(t, used.get(t.id))})
    return out


@router.get("/plans")
def plans():
    return PLANS


@router.post("/tenants/{tenant_id}/plan")
def set_plan(tenant_id: int, body: PlanIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(404, "Seller not found")
    if body.plan not in PLANS:
        raise HTTPException(422, {"errors": [f"Unknown plan. Choose one of: {', '.join(PLANS)}."]})
    t.plan, t.setup_fee, t.setup_fee_paid = body.plan, body.setup_fee, body.setup_fee_paid
    db.commit()
    return {"id": t.id, "plan": t.plan, "setup_fee": t.setup_fee, "setup_fee_paid": t.setup_fee_paid}


@router.get("/invoice.csv")
def invoice_csv(month: str | None = None, db: Session = Depends(get_db)):
    """One row per active shop for the month. Open in Excel to make the invoices."""
    month = usage.month_bounds(check_month(month))[0].strftime("%Y-%m")
    used = usage.totals_by_tenant(db, month)
    rows = [(t, month, billing.invoice(t, used.get(t.id))) for t in db.scalars(select(Tenant).where(Tenant.status == "active").order_by(Tenant.id))]
    return Response(billing.csv_text(rows), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="invoices-{month}.csv"'})


@router.post("/tenants/{tenant_id}/status")
def set_status(tenant_id: int, body: StatusIn, db: Session = Depends(get_db)):
    t = db.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(404, "Seller not found")
    t.status = body.status
    db.commit()
    return {"id": t.id, "status": t.status}


@router.get("/leads")
def leads(db: Session = Depends(get_db)):
    rows = db.scalars(select(Lead).order_by(Lead.id.desc()).limit(500))
    return [{"id": r.id, "created": r.created_at.isoformat(), "business": r.business, "name": r.name, "phone": r.phone,
             "email": r.email, "sells": r.sells, "website": r.website, "city": r.city} for r in rows]
