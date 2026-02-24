# Pipeline Dockerfile - full ML stack for FinBERT, XGBoost, sentiment pipelines.
# Heavy image (~4GB with PyTorch)
#Only build/run this when executing ML jobs.
#     
# Usage:
#   docker-compose --profile pipeline up pipeline
#    
# To run a specific pipeline manually:
#   docker-compose --profile pipeline run pipeline python -m app.services.sentiment.article_processing
#   docker-compose --profile pipeline run pipeline python -m app.services.sentiment.aggregator

FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy both files so -r requirements-api.txt resolves correctly
COPY requirements-api.txt requirements-pipeline.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements-pipeline.txt


FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

# Default: initialize the DB schema. Override CMD to run specific pipelines.
CMD ["python", "-m", "app.db_init"]
