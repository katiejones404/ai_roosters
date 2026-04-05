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

# Pre-download ProsusAI/finbert so the image is self-contained (no HuggingFace
# network call at job runtime). Model files land in /cache/huggingface which
# matches the HF_HOME env var set in docker-compose and ACA job configs.
ENV HF_HOME=/cache/huggingface
ENV PATH="/install/bin:$PATH"
ENV PYTHONPATH="/install/lib/python3.11/site-packages"
ARG PRELOAD_FINBERT=1
RUN if [ "$PRELOAD_FINBERT" = "1" ]; then \
      python -c "\
from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); \
AutoTokenizer.from_pretrained('ProsusAI/finbert'); \
print('FinBERT model cached successfully')"; \
    else \
      echo "Skipping FinBERT pre-download at build time"; \
    fi


FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
# Copy the pre-downloaded model from the builder stage
COPY --from=builder /cache/huggingface /cache/huggingface

ENV HF_HOME=/cache/huggingface

WORKDIR /app
COPY . .

# Default: initialize the DB schema. Override CMD to run specific pipelines.
CMD ["python", "-m", "app.db_init"]
