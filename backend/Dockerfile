# --- Stage 1: build wheels (needs build-essential, gcc, etc.) ---
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: slim runtime image, no build tools shipped ---
FROM python:3.11-slim AS runtime

# ping/traceroute binaries needed by network_tools.py at runtime. No
# libcap2-bin/setcap here — tried that (both at build time and at
# container startup), and Render's platform blocks CAP_SETFCAP in both
# places, confirmed by an actual failed deploy: "unable to set
# CAP_SETFCAP effective capability: Operation not permitted". Granting
# ping/traceroute raw-socket access via file capabilities isn't possible
# on Render at all, so the container runs as root instead — root already
# has CAP_NET_RAW inherently, no setcap needed. This trades away the
# non-root hardening from earlier phases specifically because Render's
# platform doesn't allow the alternative; on a host that does permit
# CAP_SETFCAP (a self-managed Docker box, a plain VM), a non-root user
# with setcap-granted binaries would still be the better design.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping traceroute \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY . .

RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh
ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Runs `alembic upgrade head` (safe/idempotent for both SQLite and
# Postgres) before starting uvicorn — see entrypoint.sh.
CMD ["./entrypoint.sh"]
