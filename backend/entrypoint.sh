#!/bin/sh
# Runs on every container start, before the app comes up. `alembic upgrade
# head` is idempotent — already-applied migrations are skipped — so this is
# safe to run on every deploy, not just the first one. It works for both
# SQLite (a trivial no-op set of DDL) and Postgres (the real target), so
# there's one code path instead of an if/else guessing which DB is in use.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
