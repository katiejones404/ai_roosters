## Stock Sense 

StockSense is a full-stack web application that provides investors with an AI-driven platform to track stock performance, analyze sentiment trends, and manage personalized portfolios. It integrates both quantitative (price and performance) and qualitative (news sentiment) data using a modern, containerized architecture.

## External Requirements

In order to build and run this project locally, you must install:

Node.js
 (for the React + Vite frontend)

Python 3.11+
 (for the FastAPI backend)

PostgreSQL
 (for database)

Docker Desktop
 (for containerized environment)

Git
 (for version control))

## Setup

### Navigate to the backend directory
### Install dependencies
### Create .env file with:
DATABASE_URL= ... 
CORS_ORIGINS=http://localhost:5173
### Run backend serve
```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload

```
---

## Frontend Setup (React + Vite)

### Navigate to the frontend directory
### Install dependencies
### Run frontend server
```bash
cd ../frontend

npm install

npm run dev

```

—

## Running

(For early framework before docker containers)
Backed: In project terminal run:

### uvicorn main:app --reload

Runs backend on [http://localhost:8000](http://localhost:8000) to view backend status

Frontend: In the project directory, you can run:

### `npm run dev`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

—
(With docker setup)

### docker-compose up -d

To stop the containers:

### docker compose down

# Deployment

### docker compose up --build

Once all containers are running, open the following URLs in your browser:

Frontend (React App): http://localhost:5173

Backend API (FastAPI): http://localhost:8000

FastAPI Docs (Swagger UI): http://localhost:8000/docs

# Testing

In 492 you will write automated tests. When you do you will need to add a
section that explains how to run them.

The unit tests are in `/test/unit`.

The behavioral tests are in `/test/casper/`.

## Testing Technology

When implemented, tests will be organized as:

/test/unit       # Unit tests
/test/casper/    # Behavioral or integration tests

Pytest for backend tests

Jest or Vitest for frontend components

GitHub Actions for continuous integration

## Running Tests

# Backend tests
pytest

# Frontend tests
npm run test


# Authors
Sofia Bacha - sofbacha01@gmail.com

Kevin Do -  kdox1023@gmail.com

Andrew Lim - andrew.lim0023@gmail.com

Connor Thiele - cthiele@email.sc.edu

Katie Jones - Katie.jones4@outlook.com

