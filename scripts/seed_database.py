"""Database Seeder Script.

Initializes the PostgreSQL database schema and populates orders, payments,
and settlements from the generated synthetic CSV files.
"""

from __future__ import annotations

import csv
import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import get_db_session, init_db
from app.models.entities import OrderModel, PaymentModel, SettlementModel
from app.reconciliation.normalizer import normalize_date, normalize_reference

DATA_DIR = os.path.join(BASE_DIR, "data", "generated")


def seed_database() -> dict[str, int]:
    print("1. Initializing database tables and pgvector extension...")
    init_db()
    print("   [OK] Tables initialized successfully.\n")

    orders_path = os.path.join(DATA_DIR, "orders.csv")
    payments_path = os.path.join(DATA_DIR, "payments.csv")
    settlements_path = os.path.join(DATA_DIR, "settlements.csv")

    if not (os.path.exists(orders_path) and os.path.exists(payments_path) and os.path.exists(settlements_path)):
        raise FileNotFoundError("Generated CSV data not found. Run `python scripts/generate_data.py` first.")

    with get_db_session() as session:
        # Clear existing data in reverse FK order
        session.query(PaymentModel).delete()
        session.query(OrderModel).delete()
        session.query(SettlementModel).delete()
        session.flush()

        # 1. Seed Orders
        orders_count = 0
        with open(orders_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                session.add(
                    OrderModel(
                        order_id=r["order_id"],
                        customer_id=r["customer_id"],
                        amount=Decimal(r["amount"]),
                        currency=r.get("currency", "INR"),
                        order_date=normalize_date(r["order_date"]),
                        status=r.get("status", "PAID"),
                    )
                )
                orders_count += 1

        session.flush()

        # 2. Seed Payments
        payments_count = 0
        with open(payments_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                session.add(
                    PaymentModel(
                        payment_id=r["payment_id"],
                        order_id=r["order_id"],
                        amount=Decimal(r["amount"]),
                        payment_date=normalize_date(r["payment_date"]),
                        payment_method=r["payment_method"],
                        status=r.get("status", "SUCCESS"),
                        raw_reference=r["reference"],
                        canonical_reference=normalize_reference(r["reference"]),
                    )
                )
                payments_count += 1

        session.flush()

        # 3. Seed Settlements
        settlements_count = 0
        with open(settlements_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                session.add(
                    SettlementModel(
                        settlement_id=r["settlement_id"],
                        payment_reference=r["payment_reference"],
                        canonical_reference=normalize_reference(r["payment_reference"]),
                        gross_amount=Decimal(r["gross_amount"]),
                        fee=Decimal(r.get("fee", "0.00")),
                        refund=Decimal(r.get("refund", "0.00")),
                        net_amount=Decimal(r["net_amount"]),
                        settlement_date=normalize_date(r["settlement_date"]),
                        status=r.get("status", "SETTLED"),
                    )
                )
                settlements_count += 1

    stats = {
        "orders_seeded": orders_count,
        "payments_seeded": payments_count,
        "settlements_seeded": settlements_count,
    }
    return stats


if __name__ == "__main__":
    print("=" * 60)
    print("  SEEDING POSTGRESQL DATABASE (pgvector/pg16)")
    print("=" * 60)
    stats = seed_database()
    print("Seeding Summary:")
    for k, v in stats.items():
        print(f" - {k:<20}: {v} records")
    print("=" * 60)
    print("Database seeding completed successfully!\n")
