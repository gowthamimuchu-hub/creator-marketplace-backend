from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models  # registers the tables
from auth import router as auth_router
from creators import router as creators_router
from briefs import router as briefs_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Creator Marketplace API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(creators_router)
app.include_router(briefs_router)


@app.get("/")
def root():
    return {"message": "Creator Marketplace API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}