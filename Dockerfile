# CEE Engine V37 PRO — Dockerfile multi-stage production-ready
# Usage :
#   docker build -t cee-engine:v37 .
#   docker run -p 5001:5001 --env-file .env cee-engine:v37

FROM python:3.12-slim AS builder

WORKDIR /build

# Install deps système minimales (pour cryptography/cffi si besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps en layer cacheable
COPY requirements.txt requirements-dev.txt* ./
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── Stage 2 : runtime minimal ───
FROM python:3.12-slim

WORKDIR /app

# User non-root (sécurité)
RUN useradd -m -u 1000 cee && \
    mkdir -p /app && chown -R cee:cee /app

# Copier les deps depuis builder
COPY --from=builder --chown=cee:cee /root/.local /home/cee/.local

# Copier le code (exclure tests, .git, etc. via .dockerignore)
COPY --chown=cee:cee . /app/

USER cee

ENV PATH=/home/cee/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_FORMAT=json \
    PORT=5001

EXPOSE ${PORT}

# Healthcheck : /health doit répondre 200
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health', timeout=3).read()" || exit 1

# Railway injecte $PORT et override via startCommand dans railway.toml
# En local : docker run -p 5001:5001 --env-file .env cee-engine:v37
CMD gunicorn api:app --bind 0.0.0.0:${PORT} --workers 2 --timeout 120
