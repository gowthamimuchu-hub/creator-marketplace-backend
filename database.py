import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
load_dotenv()
url = os.getenv("DATABASE_URL", "sqlite:///./local.db")
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
if url.startswith("postgresql://"):
    url = url.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )

engine = create_engine(
    url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()