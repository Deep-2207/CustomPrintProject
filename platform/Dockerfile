FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini .
COPY migrations migrations
COPY app app
COPY static static
# Run as an ordinary user, not root. /data holds uploads (and the SQLite file if no DATABASE_URL is given).
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser
ENV DATA_DIR=/data
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3   CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
# --proxy-headers: behind Caddy, the real visitor address arrives in a header (used by the rate limits).
# Only safe because the app port is not published to the internet (see deploy/docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
