#!/usr/bin/env bash
set -euo pipefail

: "${LOYALTY_TEST_DATABASE_URL:?LOYALTY_TEST_DATABASE_URL is required}"
export LOYALTY_DATABASE_URL="${LOYALTY_TEST_DATABASE_URL}"

alembic -c alembic_v2.ini upgrade head
pytest -q tests_v2
