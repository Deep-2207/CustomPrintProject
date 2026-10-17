#!/bin/sh
# Restores a backup made by backup.sh.   Usage:  ./restore.sh backups/db_2026-10-17_0200.sql.gz backups/files_2026-10-17_0200.tar.gz
# This REPLACES the current database and files. Stop and think before you run it.
set -eu
[ "$#" -eq 2 ] || { echo "Usage: $0 DB_BACKUP.sql.gz FILES_BACKUP.tar.gz"; exit 1; }
cd "$(dirname "$0")"
printf "This will overwrite the live database and files. Type YES to continue: "
read -r answer
[ "$answer" = "YES" ] || { echo "Cancelled."; exit 1; }
docker compose stop app
docker compose exec -T db psql -U customizer -d postgres -c "DROP DATABASE IF EXISTS customizer;" -c "CREATE DATABASE customizer OWNER customizer;"
gunzip -c "$1" | docker compose exec -T db psql -U customizer -d customizer
gunzip -c "$2" | docker compose run --rm -T --no-deps --entrypoint tar app -C /data -xf -
docker compose start app
echo "Restored. Check the site, then log in as a seller to confirm products and designs are there."
