# Product Customizer Platform

A service that lets sellers of custom products (mugs, wristbands, anything with a 3D model) give their customers a
live 3D designer. Sellers register, set up products, upload 3D models, mark print areas, and share a link.
FastAPI + SQLAlchemy on the back end (SQLite for development, PostgreSQL for production), three.js on the front end
(vendored, so there is no build step).

## Requirements
- Python 3.11 or newer
- A modern browser with WebGL (Chrome, Edge, Firefox, Safari)

## Run it (Windows PowerShell)

```powershell
cd platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OWNER_EMAIL = "you@example.com"             # creates the platform owner login on first start
$env:OWNER_PASSWORD = "a long phrase of your own"  # at least 10 characters
python -m uvicorn app.main:app --port 8800 --reload
```

macOS or Linux: activate with `source .venv/bin/activate` and use `export NAME=value` for settings.
On start-up the app brings the database up to date (Alembic migrations), refreshes the built-in products, and creates
the owner login if `OWNER_EMAIL` and `OWNER_PASSWORD` are set and no owner exists yet.
Instead of the two variables you can run `python -m app.manage create-owner you@example.com` once.
Other commands: `python -m app.manage pilot-shop "Shop name" them@example.com` (an approved free-plan shop, prints its first password) and
`python -m app.manage reset-password them@example.com` (for a seller who forgot theirs).

For demos run `python -m app.manage demo-shop`: it creates an approved shop called `ahmedabad-gifts` with the mug and
wristband published, so `/s/ahmedabad-gifts/custom-printed-mug` works.

## Pages

| Address | For | What |
| --- | --- | --- |
| `/` | Visitors | Landing page with the live demo and the seller sign-up form |
| `/account.html` | Sellers, owner | Log in, or create a seller account |
| `/dashboard.html` | Sellers | Products, 3D models, the product editor |
| `/zone-editor.html?product=ID` | Sellers | Click a part of the 3D model and mark print areas |
| `/dashboard.html#/designs` | Sellers | Designs customers saved: search, open, print files |
| `/dashboard.html#/embed` | Sellers | Allowed websites, embed code, API keys |
| `/dashboard.html#/usage` | Sellers | Designs, views, plan and the month's estimated invoice |
| `/print.html?design=ID` | Sellers | Draws the print files (transparent PNG per print area, 300 dpi) and downloads a .zip |
| `/embed/<public key>/<product>` | Seller's website | The customizer for an iframe (see `docs/EMBED_AND_API.md`); `/embed.js` is the loader script |
| `/api/v1/...` | Seller's server | Read designs with a secret key (`Authorization: Bearer sk_...`) |
| `/healthz` | Monitoring | `{"ok": true}` when the app and database answer |
| `/owner.html` | Owner | Approve sellers, set plans, download invoices (CSV), see landing-page sign-ups |
| `/s/<shop>/<product>` | Shoppers | A seller's shareable link |
| `/?product=custom-printed-mug` | Anyone | The platform's own demo products (add `&demo=1` for the demo bar) |
| `/admin.html` | Owner | Older admin page using `ADMIN_KEY` |
| `/docs` | Developers | Automatic API documentation |

## How a seller gets started
1. Create an account at `/account.html`. The shop is **pending** until the owner approves it at `/owner.html`.
2. Once approved: **New product**, then pick a ready-made mug or wristband, or one of your own uploaded 3D models.
3. In the product editor set colours, fonts, limits and starting look, then **Publish**. Share the link.
4. For your own 3D model: upload a `.glb` under **3D models** (the report says which parts can be printed on), create a
   product from it, then open the print-area editor and add areas.

5. To show the customizer on their own website: **Embed on your site**, list the website, copy the code (`docs/EMBED_AND_API.md`).
6. Customers' saved designs appear under **Designs**. Open **Print files** for a print-ready download. Set each print area's real size in mm
   (product editor, Print areas) to get 300 dpi files. **Usage and plan** shows what the month costs.

To try the 3D model flow without a model of your own, use `samples/sample-bottle.glb`
(make a new one with `python samples/make_sample_glb.py`).

3D model rules: a binary `.glb` up to 25 MB, everything embedded in the file (no outside links), no Draco, Meshopt or
Basis compression, and a UV map on every part you want to print on.

## Settings (environment variables)

| Name | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | SQLite file in `data/` | Where the data lives. PostgreSQL example below |
| `OWNER_EMAIL`, `OWNER_PASSWORD` | not set | Create the platform owner on start-up |
| `COOKIE_SECURE` | `0` | Set to `1` when the site is served over HTTPS (login cookie is then HTTPS-only) |
| `REGISTER_LIMIT_PER_HOUR` | `5` | New shops allowed per connection per hour |
| `ADMIN_KEY` | `change-me` | Secret for the older admin page. The app refuses to start with the default when `COOKIE_SECURE=1` |
| `GST_PERCENT` | `18` | GST added to invoices. The plans and prices are in `app/config.py` (`PLANS`) |
| `DATA_DIR` | `./data` | Uploaded files, design pictures, the outbox log, the SQLite file |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `NOTIFY_TO` | not set | Also email new landing-page sign-ups (they are always saved and logged) |

## PostgreSQL

```powershell
# one time, in psql as an administrator:
#   CREATE USER customizer WITH PASSWORD 'choose-a-password';
#   CREATE DATABASE customizer OWNER customizer;
$env:DATABASE_URL = "postgresql+psycopg2://customizer:choose-a-password@localhost:5432/customizer"
python -m uvicorn app.main:app --port 8800
```

The tables are created automatically on start-up. To run migrations by hand: `python -m alembic upgrade head`.
After changing a table in `app/models.py`: `python -m alembic revision --autogenerate -m "what changed"`, read the
new file in `migrations/versions/`, then upgrade. Back up with `pg_dump customizer > backup.sql`.

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest                                         # 112 tests: accounts, data isolation, products, 3D models, designs, embed, API, usage, billing, security
$env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres@localhost:5432/customizer_test"
python -m pytest                                         # the same tests on PostgreSQL (an EMPTY test database: its tables are dropped first)
```

Browser click-through checks need the server running (started with `OWNER_EMAIL=owner@example.com`,
`OWNER_PASSWORD=Owner-pass-for-dev-2026` and `REGISTER_LIMIT_PER_HOUR=50`), Microsoft Edge and `pip install websockets pillow`:

```powershell
python tests/browser_flows.py                  # shopper side: demo examples, picker, logos, save and share
python tests/browser_seller_journey.py         # seller side: register, approval, products, 3D model, print areas, phone width
python tests/browser_signup_and_mobile.py      # landing sign-up and phone layouts (adds one test sign-up; delete it afterwards)
python tests/browser_embed_and_billing.py      # embed on another website (port 8899), designs list, print-file zip, usage, password, owner billing
```

The seller-journey test creates a "Browser Test Shop" in whatever database the server uses; delete such shops when done.

## Folders

| Path | What it is |
| --- | --- |
| `app/main.py` | Start-up: migrations, built-in products, owner login, routes |
| `app/routers/` | `public` (shoppers, sign-up, pages), `auth`, `seller` and `seller_ops` (dashboard), `owner`, `embed` (iframe page and its calls), `v1` (secret-key API) |
| `app/keys.py`, `app/usage.py`, `app/billing.py`, `app/designs.py` | API keys and allowed websites; usage counters; plan maths and CSV; saving a design |
| `app/models.py`, `app/database.py`, `migrations/` | Tables, connection, Alembic migrations |
| `app/repo.py` | Database lookups. Seller queries are filtered by shop here (data isolation) |
| `app/validation.py`, `app/glb.py` | Rules for designs and products; reading `.glb` files safely |
| `app/security.py`, `app/deps.py` | Password hashing, login sessions, who may do what |
| `app/seeds.py` | The built-in mug and wristband definitions |
| `static/` | Pages. `js/` has the 3D code, `vendor/` the three.js files (kept in the repo on purpose); `embed.js` is the loader sellers put on their site |
| `deploy/` | Docker Compose (app + PostgreSQL + Caddy for HTTPS), `.env.example`, backup and restore scripts |
| `samples/` | A sample 3D bottle and the script that makes it |
| `tests/` | `pytest` tests and browser click-through checks |
| `data/` | Database file, uploads, design pictures (never committed) |

## Deploying
`deploy/` holds a Docker Compose setup (app, PostgreSQL, automatic HTTPS) and nightly backup scripts. Follow `docs/DEPLOY.md`.
The image has not been built yet in this project (see the note there): try it on a throw-away server first.

## Documents
`docs/EMBED_AND_API.md` (for sellers and their web developers), `docs/DEPLOY.md`, `docs/PILOT_KIT.md` (first sellers: offer, checklist, messages, agreement), `docs/DEMO_SCRIPT.md`.

## Status
Work in progress. See `STATUS.md` in the repository root for what is done and what is next.
