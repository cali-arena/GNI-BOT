# FastAPI API
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api ./
COPY apps/__init__.py ./apps/
COPY apps/observability ./apps/observability/
COPY apps/shared ./apps/shared/
COPY alembic ./alembic
COPY alembic.ini ./

# Note: API runs as root. For production, add non-root user; bind mounts may need chown.
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
