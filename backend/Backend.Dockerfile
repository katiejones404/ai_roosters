# 1. Build Stage
# -------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools for Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .

# Install Python packages into /install
RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

COPY . .

# 2. Runtime Stage
# -------------------------
FROM python:3.11-slim

WORKDIR /app

# Install runtime libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from build stage
COPY --from=builder /install /usr/local

EXPOSE 8000

# Health check
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]