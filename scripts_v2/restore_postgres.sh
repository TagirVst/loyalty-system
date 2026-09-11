#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /backups/file.dump" >&2
  exit 2
fi

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=loyalty}"
: "${POSTGRES_DB:=loyalty_v2}"
: "${ALLOW_DESTRUCTIVE_RESTORE:=false}"

case "$POSTGRES_DB" in
  *[!A-Za-z0-9_]*) echo "invalid POSTGRES_DB" >&2; exit 2 ;;
esac

if [ -z "${PGPASSWORD:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  export PGPASSWORD="$POSTGRES_PASSWORD"
fi

if [ "$ALLOW_DESTRUCTIVE_RESTORE" != "true" ]; then
  echo "refusing destructive restore; set ALLOW_DESTRUCTIVE_RESTORE=true" >&2
  exit 3
fi

DUMP=$1
pg_restore --list "$DUMP" >/dev/null

psql \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" \
  --dbname postgres \
  --set ON_ERROR_STOP=1 \
  --command "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB}' AND pid <> pg_backend_pid();" \
  --command "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";" \
  --command "CREATE DATABASE \"${POSTGRES_DB}\";"

pg_restore \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  "$DUMP"
