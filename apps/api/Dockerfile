# FastAPI API — build context MUST be repo root (docker-compose: context: .)
# Alembic files must be in /app so migrations run at startup (alembic -c /app/alembic.ini upgrade head).
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Alembic: copy first so build fails if context is wrong (must have alembic.ini and alembic/ at repo root)
COPY alembic.ini ./
COPY alembic ./alembic/

COPY apps/api ./
COPY apps/__init__.py ./apps/
COPY apps/observability ./apps/observability/
COPY apps/shared ./apps/shared/

# Note: API runs as root. For production, add non-root user; bind mounts may need chown.
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
