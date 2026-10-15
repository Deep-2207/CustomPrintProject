# Customizer Platform
FastAPI + SQLite backend, three.js frontend (vendored, no build step).

    pip install -r requirements.txt
    set ADMIN_KEY=your-secret        (PowerShell: $env:ADMIN_KEY="...")
    python -m uvicorn app.main:app --port 8800

- Shop page:  http://localhost:8800/?product=custom-embossed-wristband
- Admin:      http://localhost:8800/admin.html  (upload a .glb, edit zones, save)
- Docker:     docker build -t customizer . && docker run -p 8000:8000 -e ADMIN_KEY=... -v customizer-data:/data customizer
Data (SQLite, models, customer uploads, design previews) lives in DATA_DIR (default ./data).
