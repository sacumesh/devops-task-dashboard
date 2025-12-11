# Stage 1: build wheels only (no runtime bloat)
FROM python:3.11-slim AS build

# Keep Python lean and pip quiet
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src

# Build-time system deps to compile common Python wheels
# (openssl/ffi/postgres headers; no runtime packages here)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libpq-dev \
        libssl-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency manifest to maximize layer cache hits
COPY ./requirements.txt /src/requirements.txt

# Upgrade tooling and prebuild dependency wheels into a wheelhouse
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip wheel --no-cache-dir --wheel-dir /wheels -r /src/requirements.txt


# Stage 2: minimal runtime
FROM python:3.11-slim AS runtime

# Sensible defaults; disable pip cache/version check
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install only runtime shared libs (no compilers)
# - libpq5: psycopg2 runtime
# - libffi8/libssl3: cryptography, etc.
# - ca-certificates: HTTPS trust
# - curl+tini: healthcheck and signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libffi8 \
        libssl3 \
        ca-certificates \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps from prebuilt wheels (offline, reproducible)
COPY --from=build /wheels /wheels
COPY --from=build /src/requirements.txt /app/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /app/requirements.txt

# Create non-root user early and copy app owned by it
ARG APP_UID=1001
ARG APP_GID=1001
RUN groupadd -g ${APP_GID} appgroup && \
    useradd -u ${APP_UID} -g appgroup -M -d /app -s /usr/sbin/nologin appuser && \
    mkdir -p /app/.streamlit
COPY --chown=${APP_UID}:${APP_GID} app/ /app/
RUN chown -R ${APP_UID}:${APP_GID} /app

USER appuser:appgroup

ENV SERVER_PORT=5000
EXPOSE ${SERVER_PORT}

# Lightweight healthcheck (tweak if you have a dedicated health endpoint)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8501/ || exit 1

# Use tini as PID 1 for proper signal handling, then run Flask via Gunicorn
ENTRYPOINT ["tini", "--"]
CMD ["python", "main.py"]
