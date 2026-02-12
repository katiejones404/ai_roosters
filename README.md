(Web app links currently not deployed)
backend: https://ai-roosters.onrender.com/
frontend: https://ai-roosters-frontend.onrender.com/
## Stock Sense 

StockSense is a full-stack web application that provides investors with an AI-driven platform to track stock performance, analyze sentiment trends, and manage personalized portfolios. It integrates both quantitative (price and performance) and qualitative (news sentiment) data using a modern, containerized architecture.

## External Requirements 

In order to build and run our current version of StockSense locally, you'll need:  
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

## Build and Run Containers:
```bash
docker-compose up --build
```
Backend API: http://localhost:8000  
Frontend (React + Vite): http://localhost:5173

Press "Ctrl+C" to stop running or run:
```bash
docker-compose down
```

## Deployment Configurations

StockSense supports multiple deployment profiles designed to reflect different compute environments and workload characteristics.

These configurations allow the system to scale across development, staging, production, and training scenarios.
---

### Dev (CPU)
Lightweight configuration optimized for local development.
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build
```
## Staging (GPU-Lite)
Used for validation, testing, and performance evaluation with moderate GPU resources.
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.staging.gpu.yml up --build
```

## Production (CPU)
Balanced compute configuration for general inference workloads.
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up --build
```

## Production (GPU)
High-throughput configuration leveraging GPU acceleration for NLP inference and feature pipelines.
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.prod.gpu.yml up --build
```

## Training/Backtesting (GPU)
Dedicated compute profile for model retraining and experimental workloads.
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.train.yml up --build postgres trainer
```

## System Requiremments
The system shall support execution on servers with:
- Up to 64 vCPUs
- Up to 512 GB RAM
- Optional GPU acceleration

## GPU Requirements
The system shall support:
- Up to 2 GPUs per node
- GPUs with up to 80 GB VRAM

GPU acceleration is used for:
- FinBert inference
- Feature generation pipelines
- model retraining workloads

## Ram Requirments
The system shall operate within a maximum memory budget of 512 GB RAM
Memory allocation supports:
- Article ingestion
- NLP inference
- Feature engineering
- Model Training

## Storage Requirements
The system shall support up to 8 TB high-performance storage

Storage utilization includes:
- Article datasets
- Model artifacts
- Feature caches
- Logs

## Install Requirements

From ai_roosters folder:
pip install -r ./Backend/requirements.txt


## Testing

### Where the tests are

- Pytest tests (unit + API/behavior-style) live under `Testing/`.
- Sentiment behavioral (BDD) tests live under `Testing/Sentiment/behavioral/` and run with `behave`.

### Install test dependencies

From the repo root:

```bash
pip install -r ./Backend/requirements.txt
```

### Run ALL tests (pytest + sentiment behave)

From the repo root:

```bash
python ./run_testing.py
```

Common options:

- Quiet pytest output (still runs behave):

```bash
python ./run_testing.py -q
```

- Skip behave (pytest only):

```bash
python ./run_testing.py --no-behave
```

- Behave only:

```bash
python ./run_testing.py --behave-only
```

### Run just a subset (pytest)

Examples:

```bash
python ./run_testing.py Testing/Articles -v
python ./run_testing.py Testing/User -v
python ./run_testing.py Testing/Sentiment/unit -v
```


# Authors
Sofia Bacha - sofbacha01@gmail.com

Kevin Do -  kdox1023@gmail.com

Andrew Lim - andrew.lim0023@gmail.com

Connor Thiele - cthiele@email.sc.edu

Katie Jones - Katie.jones4@outlook.com

