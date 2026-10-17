#!/bin/sh
# Backs up the database and the uploaded files into ./backups, keeping the last 14 days.
# Run it from this folder (platform/deploy). To run it every night at 2 a.m., add to crontab (crontab -e):
#   0 2 * * * cd /path/to/platform/deploy && ./backup.sh >> backups/backup.log 2>&1
set -eu
cd "$(dirname "$0")"
mkdir -p backups
STAMP=$(date +%Y-%m-%d_%H%M)

docker compose exec -T db pg_dump -U customizer -d customizer | gzip > "backups/db_$STAMP.sql.gz"

# uploaded 3D models, customer pictures and design previews live in the "appdata" volume
docker compose exec -T app tar -C /data -cf - models uploads designs | gzip > "backups/files_$STAMP.tar.gz"

# a backup that is empty or truncated is worse than none: refuse to keep one
for f in "backups/db_$STAMP.sql.gz" "backups/files_$STAMP.tar.gz"; do
  gzip -t "$f" || { echo "BACKUP BROKEN: $f"; exit 1; }
done
[ "$(wc -c < "backups/db_$STAMP.sql.gz")" -gt 500 ] || { echo "BACKUP TOO SMALL: database"; exit 1; }

find backups -type f \( -name 'db_*.sql.gz' -o -name 'files_*.tar.gz' \) -mtime +14 -delete
echo "$(date) backup ok: db_$STAMP.sql.gz files_$STAMP.tar.gz"
echo "Copy ./backups to another machine or cloud storage as well: a backup on the same server does not survive losing the server."
