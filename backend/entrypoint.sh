#!/bin/sh
# Runs on every container start, as root (the Dockerfile no longer switches
# to the appuser before this script — see the comment there for why).
#
# `setcap` grants ping/traceroute the raw-socket access they need, without
# running the whole app as root. This has to happen here, at container
# *start*, not as a `docker build` step — some cloud build services
# (Render included) sandbox the build itself and block setting Linux file
# capabilities there, even though the resulting container is unrestricted
# at runtime. Safe to run on every start: setcap is idempotent, it just
# re-applies the same capability each time.
set -e

setcap cap_net_raw+ep /bin/ping
setcap cap_net_raw+ep /usr/bin/traceroute

# `alembic upgrade head` is idempotent (already-applied migrations are
# skipped), safe on every deploy, and works for both SQLite and Postgres.
# Everything from here on runs as appuser, not root — `su` (invoked by
# root) needs no password to switch to another user, so this is the
# hand-off point where root's job ends and the actual app takes over.
exec su -s /bin/sh appuser -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"
