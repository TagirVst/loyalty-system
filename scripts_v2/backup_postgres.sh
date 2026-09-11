#!/usr/bin/env sh
set -eu

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=loyalty}"
: "${POSTGRES_DB:=loyalty_v2}"
: "${BACKUP_DIR:=/backups}"

case "$POSTGRES_DB" in
  *[!A-Za-z0-9_]*) echo "invalid POSTGRES_DB" >&2; exit 2 ;;
esac

if [ -z "${PGPASSWORD:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export PGPASSWORD="$POSTGRES_PASSWORD"
fi

mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$BACKUP_DIR/${POSTGRES_DB}_${STAMP}.dump"

pg_dump \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --format custom \
  --no-owner \
  --no-privileges \
  --file "$OUT"

pg_restore --list "$OUT" >/dev/null
printf '%s\n' "$OUT"
