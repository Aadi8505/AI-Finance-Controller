"""Unit tests for Reconciliation Engine and Evaluation calculations."""

from datetime import date
from decimal import Decimal

from app.reconciliation.engine import run_deterministic_reconciliation
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement


def test_reconciliation_engine_exact_and_missing():
    # 2 Payments
    p1 = NormalizedPayment("PAY_1", "ORD_1", Decimal("5000.00"), date(2026, 1, 10), "UPI", "SUCCESS", "1001", "1001")
    p2 = NormalizedPayment("PAY_2", "ORD_2", Decimal("8000.00"), date(2026, 1, 10), "UPI", "SUCCESS", "1002", "1002")

    # 1 Matching Settlement (for p1 only)
    s1 = NormalizedSettlement("SET_1", "1001", "1001", Decimal("5000.00"), Decimal("0.00"), Decimal("0.00"), Decimal("5000.00"), date(2026, 1, 10), "SETTLED")

    res = run_deterministic_reconciliation([p1, p2], [s1])

    assert res.total_processed == 2
    assert len(res.matched) == 1
    assert res.matched[0].payment_id == "PAY_1"
    assert res.matched[0].settlement_id == "SET_1"

    assert len(res.exceptions) == 1
    assert res.exceptions[0].payment_id == "PAY_2"
    assert res.exceptions[0].reason_code == "MISSING_SETTLEMENT"
