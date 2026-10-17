"""Settings, read once from environment variables. See README for the list."""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA_DIR", BASE / "data"))
MODELS, UPLOADS, DESIGNS = DATA / "models", DATA / "uploads", DATA / "designs"
for _d in (MODELS, UPLOADS, DESIGNS):
    _d.mkdir(parents=True, exist_ok=True)

# SQLite works with no setup (development). For PostgreSQL set, for example:
#   DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/customizer
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(DATA / 'app.db').as_posix()}")

ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")            # legacy admin page and sign-up list
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"      # set to 1 when the site is served over HTTPS
SESSION_DAYS = 7
REGISTER_LIMIT_PER_HOUR = int(os.environ.get("REGISTER_LIMIT_PER_HOUR", "5"))   # new shops per connection per hour
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "").strip().lower()  # optional: creates the platform owner at start-up
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")

MAX_MODEL_BYTES = 25 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_PX = 300            # shorter side; smaller artwork prints blurry
MAX_PREVIEW_BYTES = 3 * 1024 * 1024
HEAVY_TRIANGLES = 200_000     # warn above this many triangles in a model

ALLOWED_FONTS = ["Arial", "Impact", "Georgia", "Courier New", "Trebuchet MS"]
RESERVED_SLUGS = {"admin", "api", "s", "files", "www", "owner", "dashboard", "account", "static", "docs", "landing",
                  "login", "register", "css", "js", "vendor", "app", "platform", "demo", "help", "support"}

# Plans (amounts in INR per month). "included" designs are free each month; extra designs cost "overage" each.
# Edit this table to change pricing; the owner picks a plan per shop on the owner screen.
PLANS = {
    "pilot":   {"label": "Pilot (free)", "monthly": 0,    "included": 100,  "overage": 0},
    "starter": {"label": "Starter",      "monthly": 999,  "included": 300,  "overage": 3},
    "growth":  {"label": "Growth",       "monthly": 2499, "included": 1500, "overage": 2},
}
GST_PERCENT = int(os.environ.get("GST_PERCENT", "18"))
