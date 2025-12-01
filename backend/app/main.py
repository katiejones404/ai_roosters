from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Backend is working!", "status": "healthy"}

@app.get("/health")
def health_check():
    return{"status": "healthy", "database": "connected"}