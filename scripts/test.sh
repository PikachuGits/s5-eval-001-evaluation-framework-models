#!/usr/bin/env bash
# Run the test suite against a real PostgreSQL 16 database.
#
#   TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DB_NAME_WITH_TEST' \
#     ./scripts/test.sh
#
# The fixture drops and recreates the public schema.  The database name must
# contain "test"; see tests/conftest.py.
#
# Set EVIDENCE_OUT=<path> to also write a sanitised report (absolute repo paths
# are replaced with "." so the evidence file never leaks a local layout).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -z "${TEST_DATABASE_URL:-}" ]; then
  echo "TEST_DATABASE_URL is required, e.g. postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DB_NAME_WITH_TEST" >&2
  exit 2
fi

export DATABASE_URL="$TEST_DATABASE_URL"

if [ -n "${EVIDENCE_OUT:-}" ]; then
  .venv/bin/python -m pytest -v "$@" 2>&1 | sed "s|$DIR|.|g" | tee "$EVIDENCE_OUT"
else
  .venv/bin/python -m pytest -v "$@"
fi
