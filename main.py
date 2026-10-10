from fastapi import FastAPI
from database import engine, Base
import models  # registers the tables

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Creator Marketplace API")

@app.get("/health")
def health():
    return {"status": "ok"}