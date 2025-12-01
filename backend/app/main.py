from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth  # ← ADD THIS LINE

app = FastAPI(
    title="Stock Portfolio API",
    description="API for stock portfolio management with authentication",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router ← ADD THIS LINE
app.include_router(auth.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Backend is working!", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": "connected"}