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

# ping/traceroute binaries needed by network_tools.py at runtime only.
# libcap2-bin + setcap below let a non-root user open the raw sockets
# ping/traceroute need, instead of running the whole container as root.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping traceroute libcap2-bin \
    && setcap cap_net_raw+ep /bin/ping \
    && setcap cap_net_raw+ep /usr/bin/traceroute \
    && apt-get purge -y libcap2-bin && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY . .

RUN mkdir -p /app/data && chown -R appuser:appuser /app && chmod +x /app/entrypoint.sh
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Runs `alembic upgrade head` (safe/idempotent for both SQLite and
# Postgres) before starting uvicorn — see entrypoint.sh.
CMD ["./entrypoint.sh"]
