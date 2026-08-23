"""Unit tests for PostgreSQL & pgvector Database Connection and ORM Queries."""

import os
import pytest
from sqlalchemy import text
from app.db.database import get_db_session, init_db
from app.models.entities import OrderModel, PaymentModel, SettlementModel


@pytest.fixture(scope="module")
def setup_test_db():
    init_db()


def test_database_connection_and_pgvector(setup_test_db):
    with get_db_session() as session:
        bind = session.get_bind()
        if "postgresql" in str(bind.url):
            result = session.execute(text("SELECT extname FROM pg_extension WHERE extname='vector';")).fetchone()
            assert result is not None
            assert result[0] == "vector"
        else:
            result = session.execute(text("SELECT 1;")).fetchone()
            assert result is not None


def test_query_seeded_orders(setup_test_db):
    with get_db_session() as session:
        count = session.query(OrderModel).count()
        assert count > 0
        order = session.query(OrderModel).first()
        assert order.order_id.startswith("ORD_")
        assert order.amount > 0


def test_query_payments_and_relationships(setup_test_db):
    with get_db_session() as session:
        payment = session.query(PaymentModel).first()
        assert payment is not None
        assert payment.payment_id.startswith("PAY_")
        assert payment.order is not None
        assert payment.canonical_reference != ""


def test_query_settlements(setup_test_db):
    with get_db_session() as session:
        settlement = session.query(SettlementModel).first()
        assert settlement is not None
        assert settlement.settlement_id.startswith("SET_")
        assert settlement.gross_amount > 0
