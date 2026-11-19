FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLOUD_HOST=0.0.0.0 \
    CLOUD_PORT=4780

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY packages/contracts /app/packages/contracts
COPY packages/provider-adapters /app/packages/provider-adapters
COPY services /app/services
COPY infrastructure/database/postgres /app/infrastructure/database/postgres

RUN pip install --no-cache-dir \
    /app/packages/contracts \
    /app/packages/provider-adapters \
    /app/services \
    "redis>=5.0.0"

EXPOSE 4780

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4780/health', timeout=2)" || exit 1

CMD ["python", "-m", "project_t_cloud_services"]
