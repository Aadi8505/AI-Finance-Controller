"""Database connection, engine configuration, and session lifecycle management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://finance:finance123@127.0.0.1:5435/ai_finance_controller",
)

# Convert asyncpg/other prefixes to psycopg2 if needed for synchronous engine
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(
    SYNC_DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Initialize database tables and pgvector extension from schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with engine.connect() as conn:
        # Execute schema
        conn.execute(text(schema_sql))
        conn.commit()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for transactional database sessions."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session injection."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
