# Putting it on the internet (about one hour, about ₹500 to ₹800 a month)

This runs the app, PostgreSQL and an automatic HTTPS certificate on **one small server** with Docker.
The files are in `platform/deploy/`.

> **Honest status:** the Docker files were written and checked for syntax (`docker compose config`, script parsing, the production start-up guard),
> but the image has **not been built or run** in this project yet, because the Docker engine was not running on the development laptop.
> Do the "first deploy" below on a throw-away server first and fix anything that comes up before a real seller depends on it.

## What you need

| Item | Notes | Rough cost |
| --- | --- | --- |
| A small Linux server (1 to 2 GB RAM, 20 GB disk) | Ubuntu 22.04 or 24.04. Any provider: Hetzner, DigitalOcean, Vultr, AWS Lightsail, or an Indian host. Pick a region near India for speed (Mumbai or Singapore). Check current prices; they change. | ₹400 to ₹700 a month |
| A domain name | e.g. `customize.yourbrand.in` (a subdomain of a domain you own is fine) | ₹600 to ₹1,000 a year |
| An email address for sign-up alerts (optional) | Gmail with an app password works | free |

Free uptime watching: UptimeRobot or similar, pointing at `https://YOUR-DOMAIN/healthz` (answers `{"ok": true}`).

## First deploy

1. **Create the server** and log in over SSH. Use SSH keys, not a password. Turn on the provider's firewall: allow ports 22, 80 and 443 only.
2. **Point the domain** at the server: an `A` record `customize` → the server's IP. Wait until `ping customize.yourbrand.in` shows that IP.
3. **Install Docker:** `curl -fsSL https://get.docker.com | sh`
4. **Get the code:** `git clone <your repository> app && cd app/platform/deploy`
5. **Settings:** `cp .env.example .env`, then edit `.env` and fill **every** line: `DOMAIN`, `DB_PASSWORD` (long random), `ADMIN_KEY` (long random), `OWNER_EMAIL`, `OWNER_PASSWORD`.
   Generate random values with `openssl rand -base64 24`. The app refuses to start on a live site (`COOKIE_SECURE=1`) if `ADMIN_KEY` is still the default.
6. **Start:** `docker compose up -d --build`. The first build takes a few minutes.
7. **Check:** `docker compose ps` (all three "running"), `docker compose logs app` (look for "Application startup complete"), then open `https://YOUR-DOMAIN`.
   Caddy needs a minute to get the certificate. If it fails, the domain does not point at the server yet, or ports 80/443 are blocked.
8. **Log in as the owner** at `/account.html` with `OWNER_EMAIL`. Then edit `.env` and delete the `OWNER_PASSWORD` line, and run `docker compose up -d`.
9. **Make your first pilot shop:**
   `docker compose exec app python -m app.manage pilot-shop "Shop Name" owner@theirshop.com` prints their login (shown once).
10. **Set up backups** (next section) and **test a restore** before you call it done.

## Backups (do not skip)

`./backup.sh` saves the database and the uploaded files into `platform/deploy/backups/` and keeps 14 days. Run it nightly:

```
crontab -e
0 2 * * * cd /home/YOUR-USER/app/platform/deploy && ./backup.sh >> backups/backup.log 2>&1
```

A backup on the same server is lost if the server is lost. **Copy `backups/` somewhere else** at least weekly: another server (`rsync`), Google Drive, or the
provider's snapshot feature. **Practise the restore** once on a spare server with `./restore.sh <db file> <files file>`: a backup you have never restored is a hope, not a backup.

## Updating the site

```
cd ~/app && git pull && cd platform/deploy && ./backup.sh && docker compose up -d --build
```

Database changes (migrations) are applied automatically on start. Take the backup first.

## Day-to-day

| Task | Command (from `platform/deploy`) |
| --- | --- |
| See what is running | `docker compose ps` |
| Read the app's log | `docker compose logs -f app` |
| A seller forgot their password | `docker compose exec app python -m app.manage reset-password their@email.com` |
| Restart | `docker compose restart app` |
| Stop everything | `docker compose down` (data stays in volumes) |
| Invoices for the month | Owner page, **Plans and invoices**, **Download invoices (CSV)** |

## Security checklist before the first real seller

- [ ] Only ports 22, 80, 443 are open. Port 8000 is **not** published (the compose file does not publish it).
- [ ] `.env` is not in git and only you can read it (`chmod 600 .env`).
- [ ] `ADMIN_KEY` and `DB_PASSWORD` are long random values, and `OWNER_PASSWORD` is removed from `.env` after the first start.
- [ ] You can log in as the owner, and a test seller **cannot** open `/owner.html` or `/api/owner/tenants`.
- [ ] HTTPS works and `http://` redirects to it (Caddy does this by default).
- [ ] A backup ran, and you restored it once on a spare machine.
- [ ] Server updates: `sudo apt update && sudo apt upgrade` monthly, or turn on unattended upgrades.
- [ ] Uptime monitor on `/healthz` is sending alerts to your phone.

## Things to know

- **One server, one process.** Rate limits are kept in memory, so they reset when the app restarts. That is fine for a pilot. Past roughly a few thousand designs a day, move them to Redis.
- **Uploaded files** (3D models, customer pictures, previews) live in the `appdata` Docker volume, are included in `backup.sh`, and are served by the app itself.
  Seller 3D models are public by their (random) file address. Do not treat a model as confidential.
- **Client addresses.** The app trusts the `X-Forwarded-For` header because only Caddy can reach it. If you ever publish the app's port directly, remove `--proxy-headers` from the `Dockerfile`.
- **Email.** Only landing-page sign-up alerts are sent (if `SMTP_*` is set). There is no password-reset email yet: use `reset-password` above.
