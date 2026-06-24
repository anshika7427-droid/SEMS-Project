# Stage 1: Build stage to install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final runtime stage
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Copy installed dependencies from builder stage
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Ensure data and storage directories are created and owned by appuser
RUN mkdir -p /app/data /app/storage /app/storage/avatars /app/storage/resources && \
    chown -R appuser:appuser /app/data /app/storage

# Copy application files
COPY --chown=appuser:appuser app/ ./app
COPY --chown=appuser:appuser frontend/ ./frontend
COPY --chown=appuser:appuser alembic/ ./alembic
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser run.py .

USER appuser

EXPOSE 8000

# Start server using gunicorn with config from run.py
CMD ["gunicorn", "app.main:app", "-c", "run.py", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
