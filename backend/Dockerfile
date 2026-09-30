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

# ping/traceroute binaries needed by network_tools.py at runtime.
# libcap2-bin (setcap) is kept installed permanently, not purged after use
# like before — the actual `setcap` call now runs in entrypoint.sh at
# container *start*, not here at *build* time. Some cloud build services
# (Render included) run `docker build` in a sandbox that blocks setting
# Linux file capabilities, even though the resulting *container* at
# runtime allows it fine — so this step only installs the tools; granting
# the capability is deferred to first boot.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping traceroute libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY . .

RUN mkdir -p /app/data && chown -R appuser:appuser /app && chmod +x /app/entrypoint.sh
# Deliberately NOT switching to appuser here (no `USER appuser`) — the
# container needs to start as root so entrypoint.sh can run `setcap`,
# then it drops to appuser itself for the actual app process. See
# entrypoint.sh for exactly where that handoff happens.
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Runs `alembic upgrade head` (safe/idempotent for both SQLite and
# Postgres) before starting uvicorn — see entrypoint.sh.
CMD ["./entrypoint.sh"]
