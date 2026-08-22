"""Unit tests for Deterministic Safety Validator."""

from datetime import date
from decimal import Decimal
import pytest

from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement
from app.reconciliation.validator import SafetyValidator


def _make_payment(pid="PAY_1", amt="5000.00", pdate=date(2026, 1, 10)) -> NormalizedPayment:
    return NormalizedPayment(
        payment_id=pid,
        order_id="ORD_1",
        amount=Decimal(amt),
        payment_date=pdate,
        payment_method="CARD",
        status="SUCCESS",
        raw_reference="1001",
        canonical_reference="1001",
    )


def _make_settlement(
    sid="SET_1",
    gross="5000.00",
    fee="100.00",
    refund="0.00",
    net="4900.00",
    sdate=date(2026, 1, 11),
) -> NormalizedSettlement:
    return NormalizedSettlement(
        settlement_id=sid,
        payment_reference="1001",
        canonical_reference="1001",
        gross_amount=Decimal(gross),
        fee=Decimal(fee),
        refund=Decimal(refund),
        net_amount=Decimal(net),
        settlement_date=sdate,
        status="SETTLED",
    )


class TestSafetyValidator:
    def test_valid_match(self):
        validator = SafetyValidator(min_confidence=Decimal("0.85"))
        p = _make_payment()
        s = _make_settlement()

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.95,
            claimed_payments=set(),
            claimed_settlements=set(),
        )
        assert res.is_valid is True
        assert res.validated_action == "MATCH"
        assert res.discrepancy == Decimal("0.00")

    def test_reject_already_claimed_payment(self):
        validator = SafetyValidator()
        p = _make_payment(pid="PAY_CLAIMED")
        s = _make_settlement()

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.95,
            claimed_payments={"PAY_CLAIMED"},
            claimed_settlements=set(),
        )
        assert res.is_valid is False
        assert res.validated_action == "MANUAL_REVIEW"
        assert any("already been claimed" in e for e in res.validation_errors)

    def test_reject_already_claimed_settlement(self):
        validator = SafetyValidator()
        p = _make_payment()
        s = _make_settlement(sid="SET_CLAIMED")

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.95,
            claimed_payments=set(),
            claimed_settlements={"SET_CLAIMED"},
        )
        assert res.is_valid is False
        assert res.validated_action == "MANUAL_REVIEW"
        assert any("Settlement SET_CLAIMED has already been claimed" in e for e in res.validation_errors)

    def test_reject_temporal_violation(self):
        validator = SafetyValidator()
        p = _make_payment(pdate=date(2026, 1, 10))
        # Settlement is dated BEFORE payment
        s = _make_settlement(sdate=date(2026, 1, 8))

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.95,
            claimed_payments=set(),
            claimed_settlements=set(),
        )
        assert res.is_valid is False
        assert any("Temporal violation" in e for e in res.validation_errors)

    def test_reject_amount_conservation_failure(self):
        validator = SafetyValidator()
        p = _make_payment(amt="5000.00")
        # Net + fee = 4000 != 5000
        s = _make_settlement(gross="4000.00", fee="100.00", net="3900.00")

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.95,
            claimed_payments=set(),
            claimed_settlements=set(),
        )
        assert res.is_valid is False
        assert res.discrepancy == Decimal("1000.00")
        assert any("Amount conservation failure" in e for e in res.validation_errors)

    def test_reject_low_confidence_match(self):
        validator = SafetyValidator(min_confidence=Decimal("0.85"))
        p = _make_payment()
        s = _make_settlement()

        res = validator.validate_match(
            payment=p,
            settlement=s,
            recommended_action="MATCH",
            confidence=0.70,  # Below 0.85
            claimed_payments=set(),
            claimed_settlements=set(),
        )
        assert res.is_valid is False
        assert any("Confidence score" in e for e in res.validation_errors)
