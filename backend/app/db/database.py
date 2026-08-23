"""Database connection, engine configuration, and session lifecycle management."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "data", "finance_local.db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://finance:finance123@127.0.0.1:5435/ai_finance_controller",
)
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

Base = declarative_base()


def _create_working_engine():
    """Attempt PostgreSQL connection; fallback to SQLite if offline."""
    try:
        pg_engine = create_engine(
            SYNC_DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2},
        )
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return pg_engine
    except Exception:
        # Fallback to local SQLite database
        os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
        sqlite_url = f"sqlite:///{SQLITE_DB_PATH}"
        return create_engine(
            sqlite_url,
            connect_args={"check_same_thread": False},
        )


engine = _create_working_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables and seed if SQLite."""
    global engine, SessionLocal
    # If using postgresql, run schema.sql
    if "postgresql" in str(engine.url):
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        with engine.connect() as conn:
            conn.execute(text(schema_sql))
            conn.commit()
    else:
        # SQLite schema creation via entities
        import app.models.entities as entities  # noqa: F401
        Base.metadata.create_all(engine)
        # Auto seed if empty
        _seed_sqlite_if_empty()


def _seed_sqlite_if_empty():
    import pandas as pd
    from app.models.entities import OrderModel, PaymentModel, SettlementModel
    import csv

    with SessionLocal() as session:
        if session.query(OrderModel).count() == 0:
            orders_csv = os.path.join(BASE_DIR, "data", "generated", "orders.csv")
            payments_csv = os.path.join(BASE_DIR, "data", "generated", "payments.csv")
            settlements_csv = os.path.join(BASE_DIR, "data", "generated", "settlements.csv")

            if os.path.exists(orders_csv):
                df_orders = pd.read_csv(orders_csv)
                for _, r in df_orders.iterrows():
                    session.merge(OrderModel(
                        order_id=str(r["order_id"]),
                        customer_id=str(r["customer_id"]),
                        amount=r["amount"],
                        currency=str(r["currency"]),
                        order_date=pd.to_datetime(r["order_date"]).date(),
                        status=str(r["status"]),
                    ))
                session.commit()

            if os.path.exists(payments_csv):
                df_pay = pd.read_csv(payments_csv)
                for _, r in df_pay.iterrows():
                    raw_ref = str(r["reference"]) if pd.notna(r["reference"]) else ""
                    canon_ref = raw_ref.replace("RZP_REF_", "").replace("RZPREF", "").replace("RZP/REF/", "").replace("PAY_", "")
                    session.merge(PaymentModel(
                        payment_id=str(r["payment_id"]),
                        order_id=str(r["order_id"]),
                        amount=r["amount"],
                        payment_date=pd.to_datetime(r["payment_date"]).date(),
                        payment_method=str(r["payment_method"]),
                        status=str(r["status"]),
                        raw_reference=raw_ref,
                        canonical_reference=canon_ref,
                    ))
                session.commit()

            if os.path.exists(settlements_csv):
                df_settle = pd.read_csv(settlements_csv)
                for _, r in df_settle.iterrows():
                    raw_ref = str(r["payment_reference"]) if pd.notna(r["payment_reference"]) else ""
                    canon_ref = raw_ref.replace("RZP_REF_", "").replace("RZPREF", "").replace("RZP/REF/", "").replace("PAY_", "")
                    session.merge(SettlementModel(
                        settlement_id=str(r["settlement_id"]),
                        payment_reference=raw_ref,
                        canonical_reference=canon_ref,
                        gross_amount=r["gross_amount"],
                        fee=r.get("fee", 0.0),
                        refund=r.get("refund", 0.0),
                        net_amount=r["net_amount"],
                        settlement_date=pd.to_datetime(r["settlement_date"]).date(),
                        status=str(r["status"]),
                    ))
                session.commit()


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

