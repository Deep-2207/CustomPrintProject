# Product Customizer Platform

A live 3D product customizer (wristband first, mug next) with a Python API.
FastAPI + SQLite on the back end, three.js on the front end (vendored, so there is no build step).

## Requirements
- Python 3.11 or newer
- A modern browser with WebGL (Chrome, Edge, Firefox, Safari)

## Run it (Windows PowerShell)

```powershell
cd platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADMIN_KEY = "pick-a-long-secret"     # protects the admin pages; default is "change-me"
python -m uvicorn app.main:app --port 8800 --reload
```

macOS or Linux: activate with `source .venv/bin/activate` and set the key with `export ADMIN_KEY=...`.

Then open:
- Shop page: http://localhost:8800/?product=custom-embossed-wristband
- Admin page: http://localhost:8800/admin.html (enter your ADMIN_KEY)
- API docs (auto-generated): http://localhost:8800/docs

The first start creates `platform/data/` with the SQLite database and uploaded files.
That folder is git-ignored; delete it to reset to a clean state.

## Folders

| Path | What it is |
| --- | --- |
| `app/main.py` | The API: products, uploads, designs, validation |
| `static/product.html`, `static/js/` | The customer page and the 3D customizer |
| `static/admin.html` | Product and 3D model admin |
| `static/vendor/` | three.js files (kept in the repo on purpose) |
| `data/` | Database and uploads (never committed) |

## Settings (environment variables)

| Name | Default | Purpose |
| --- | --- | --- |
| `ADMIN_KEY` | `change-me` | Secret for admin endpoints. Always set it outside your laptop. |
| `DATA_DIR` | `./data` | Where the database and files live |

## Docker

```
docker build -t customizer .
docker run -p 8000:8000 -e ADMIN_KEY=your-secret -v customizer-data:/data customizer
```

## Status
Proof of concept. Build plan: see the SRS v2 day-by-day plan (Day 1 is this repo setup).
