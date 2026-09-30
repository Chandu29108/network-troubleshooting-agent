#!/bin/sh
# Runs on every container start. `alembic upgrade head` is idempotent
# (already-applied migrations are skipped), safe on every deploy, and works
# for both SQLite and Postgres.
#
# Runs as root (see the Dockerfile comment for why: Render blocks the
# capability needed to run ping/traceroute as a non-root user, so root is
# the only option that works on this specific platform).
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
