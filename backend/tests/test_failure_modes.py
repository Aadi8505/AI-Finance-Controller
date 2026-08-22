"""Comprehensive Failure Mode & Adversarial Stress Tests."""

from datetime import date
from decimal import Decimal
import pytest

from app.db.database import get_db_session, init_db
from app.reconciliation.normalizer import (
    NormalizedPayment,
    NormalizedSettlement,
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_reference,
)
from app.reconciliation.validator import SafetyValidator


@pytest.fixture(scope="module", autouse=True)
def setup_failure_db():
    init_db()


class TestAdversarialInputs:
    def test_reference_prefixes_and_dirty_separators(self):
        assert normalize_reference("  REF-99-01_ABC  ") == "9901ABC"
        assert normalize_reference("PAY_123/456") == "123456"
        assert normalize_reference(None) == ""

    def test_malformed_amount_string(self):
        with pytest.raises(ValueError):
            normalize_amount("invalid_non_numeric")

    def test_currency_symbol_normalization(self):
        assert normalize_currency("₹") == "INR"
        assert normalize_currency("INR") == "INR"
        assert normalize_currency("$") == "USD"
        assert normalize_currency("EUR") == "EUR"

    def test_invalid_date_format_handling(self):
        with pytest.raises(ValueError):
            normalize_date("32-13-2026")


class TestSafetyBarrierUnderAttack:
    def test_reject_extreme_fee_hallucination(self):
        validator = SafetyValidator()
        p = NormalizedPayment(
            payment_id="PAY_ADV_1",
            order_id="ORD_ADV_1",
            amount=Decimal("10000.00"),
            payment_date=date(2026, 1, 10),
            payment_method="CARD",
            status="SUCCESS",
            raw_reference="ADV1",
            canonical_reference="ADV1",
        )
        # Attempt to match with settlement of net 1000.00 and fee 100.00 (8900 missing)
        s = NormalizedSettlement(
            settlement_id="SET_ADV_1",
            payment_reference="ADV1",
            canonical_reference="ADV1",
            gross_amount=Decimal("1100.00"),
            fee=Decimal("100.00"),
            refund=Decimal("0.00"),
            net_amount=Decimal("1000.00"),
            settlement_date=date(2026, 1, 11),
            status="SETTLED",
        )

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.99,
            claimed_payments=set(),
            claimed_settlements=set(),
        )
        assert res.is_valid is False
        assert res.validated_action == "MANUAL_REVIEW"
        assert res.discrepancy == Decimal("8900.00")

    def test_reject_extreme_future_lag(self):
        validator = SafetyValidator()
        p = NormalizedPayment(
            payment_id="PAY_ADV_2",
            order_id="ORD_ADV_2",
            amount=Decimal("5000.00"),
            payment_date=date(2026, 1, 1),
            payment_method="UPI",
            status="SUCCESS",
            raw_reference="ADV2",
            canonical_reference="ADV2",
        )
        # Settle 300 days in the future
        s = NormalizedSettlement(
            settlement_id="SET_ADV_2",
            payment_reference="ADV2",
            canonical_reference="ADV2",
            gross_amount=Decimal("5000.00"),
            fee=Decimal("0.00"),
            refund=Decimal("0.00"),
            net_amount=Decimal("5000.00"),
            settlement_date=date(2026, 11, 1),
            status="SETTLED",
        )

        from app.agents.tools.financial_tools import verify_settlement_window
        window_check = verify_settlement_window(p.payment_date, s.settlement_date)
        assert window_check["is_within_policy"] is False
        assert window_check["delta_days"] == 304
