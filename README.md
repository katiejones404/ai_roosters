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

