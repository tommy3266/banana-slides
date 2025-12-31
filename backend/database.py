"""
Database dependency for FastAPI
"""
from typing import Generator
from sqlalchemy.orm import Session
from models import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI endpoints.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()