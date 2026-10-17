"""Usage counters. One row per shop, day (India time) and kind: view | design | export."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import UsageDaily

IST = timezone(timedelta(hours=5, minutes=30))
KINDS = ("view", "design", "export")


def today() -> date:
    return datetime.now(IST).date()


def bump(db: Session, tenant_id: int, kind: str, n: int = 1) -> None:
    """Adds n to today's counter. Safe when two requests arrive together (the loser retries as an update)."""
    day = today()
    where = (UsageDaily.tenant_id == tenant_id, UsageDaily.day == day, UsageDaily.kind == kind)
    done = db.execute(update(UsageDaily).where(*where).values(count=UsageDaily.count + n)).rowcount
    if not done:
        try:
            with db.begin_nested():
                db.add(UsageDaily(tenant_id=tenant_id, day=day, kind=kind, count=n))
        except IntegrityError:
            db.execute(update(UsageDaily).where(*where).values(count=UsageDaily.count + n))
    db.commit()


def month_bounds(month: str | None) -> tuple[date, date]:
    """'2026-10' -> (first day, first day of next month). Defaults to the current month."""
    if month:
        y, m = (int(x) for x in month.split("-"))
        first = date(y, m, 1)
    else:
        t = today()
        first = date(t.year, t.month, 1)
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return first, nxt


def per_day(db: Session, tenant_id: int, month: str | None) -> dict:
    first, nxt = month_bounds(month)
    rows = db.execute(select(UsageDaily.day, UsageDaily.kind, UsageDaily.count)
                      .where(UsageDaily.tenant_id == tenant_id, UsageDaily.day >= first, UsageDaily.day < nxt)).all()
    days: dict[str, dict] = {}
    totals = {k: 0 for k in KINDS}
    for d, k, c in rows:
        days.setdefault(d.isoformat(), {})[k] = c
        totals[k] = totals.get(k, 0) + c
    return {"month": first.strftime("%Y-%m"), "days": days, "totals": totals}


def totals_by_tenant(db: Session, month: str | None) -> dict[int, dict]:
    first, nxt = month_bounds(month)
    rows = db.execute(select(UsageDaily.tenant_id, UsageDaily.kind, func.sum(UsageDaily.count))
                      .where(UsageDaily.day >= first, UsageDaily.day < nxt).group_by(UsageDaily.tenant_id, UsageDaily.kind)).all()
    out: dict[int, dict] = {}
    for t, k, c in rows:
        out.setdefault(t, {k2: 0 for k2 in KINDS})[k] = int(c)
    return out
