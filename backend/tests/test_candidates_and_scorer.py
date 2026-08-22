"""Unit tests for Candidate Generation, Multi-factor Scorer, and Confidence Router."""

from datetime import date
from decimal import Decimal

from app.reconciliation.candidates import generate_candidates
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement
from app.reconciliation.scorer import (
    compute_amount_score,
    compute_date_score,
    compute_reference_similarity,
    score_and_rank_candidates,
    score_candidate,
)


def _make_payment(
    pid="PAY_1001",
    amt="5000.00",
    pdate=date(2026, 1, 10),
    raw_ref="RZP_REF_1001",
    can_ref="1001",
    method="UPI",
) -> NormalizedPayment:
    return NormalizedPayment(
        payment_id=pid,
        order_id="ORD_1001",
        amount=Decimal(amt),
        payment_date=pdate,
        payment_method=method,
        status="SUCCESS",
        raw_reference=raw_ref,
        canonical_reference=can_ref,
    )


def _make_settlement(
    sid="SET_9001",
    gross="5000.00",
    fee="0.00",
    refund="0.00",
    net="5000.00",
    sdate=date(2026, 1, 10),
    raw_ref="RZP_REF_1001",
    can_ref="1001",
    status="SETTLED",
) -> NormalizedSettlement:
    return NormalizedSettlement(
        settlement_id=sid,
        payment_reference=raw_ref,
        canonical_reference=can_ref,
        gross_amount=Decimal(gross),
        fee=Decimal(fee),
        refund=Decimal(refund),
        net_amount=Decimal(net),
        settlement_date=sdate,
        status=status,
    )


class TestCandidateGeneration:
    def test_window_and_amount_filter(self):
        p = _make_payment(pdate=date(2026, 1, 10), amt="5000.00")
        
        # Valid candidate: within 7 days, right amount
        s1 = _make_settlement(sid="SET_1", sdate=date(2026, 1, 11), net="5000.00")
        # Invalid candidate: outside 7 days
        s2 = _make_settlement(sid="SET_2", sdate=date(2026, 1, 20), net="5000.00")
        # Invalid candidate: completely different amount
        s3 = _make_settlement(sid="SET_3", sdate=date(2026, 1, 11), net="15000.00", gross="15000.00")
        # Valid candidate: with fee deduction (net 4900 is within 25%)
        s4 = _make_settlement(sid="SET_4", sdate=date(2026, 1, 12), gross="5000.00", fee="100.00", net="4900.00")

        candidates = generate_candidates(p, [s1, s2, s3, s4], window_days=7)
        ids = [c.settlement_id for c in candidates]
        
        assert "SET_1" in ids
        assert "SET_4" in ids
        assert "SET_2" not in ids
        assert "SET_3" not in ids


class TestScorerComponents:
    def test_reference_similarity(self):
        assert compute_reference_similarity("1001", "1001") == Decimal("1.00")
        assert compute_reference_similarity("1001", "1001_DUP") == Decimal("0.90")
        assert compute_reference_similarity("1001", "9999") < Decimal("0.50")

    def test_amount_score_exact(self):
        p = _make_payment(amt="5000.00")
        s = _make_settlement(net="5000.00", gross="5000.00", fee="0.00")
        score, _ = compute_amount_score(p, s)
        assert score == Decimal("1.00")

    def test_amount_score_with_fee(self):
        p = _make_payment(amt="5000.00", method="CARD")
        # 2% fee = 100
        s = _make_settlement(gross="5000.00", fee="100.00", net="4900.00")
        score, _ = compute_amount_score(p, s)
        assert score == Decimal("0.95")

    def test_date_score(self):
        p = _make_payment(pdate=date(2026, 1, 10))
        # T+0
        s0 = _make_settlement(sdate=date(2026, 1, 10))
        assert compute_date_score(p, s0)[0] == Decimal("1.00")
        # T+2
        s2 = _make_settlement(sdate=date(2026, 1, 12))
        assert compute_date_score(p, s2)[0] == Decimal("0.85")
        # Prior date (invalid)
        sp = _make_settlement(sdate=date(2026, 1, 8))
        assert compute_date_score(p, sp)[0] == Decimal("0.00")


class TestConfidenceRouting:
    def test_high_confidence_exact_match(self):
        p = _make_payment(amt="10000.00", can_ref="8841", pdate=date(2026, 1, 10))
        s = _make_settlement(net="10000.00", can_ref="8841", sdate=date(2026, 1, 10))

        result = score_candidate(p, s)
        assert result.score_breakdown.total_score == Decimal("1.0000")
        assert result.routing_tier == "HIGH_CONFIDENCE"

    def test_medium_confidence_fee_and_delay(self):
        p = _make_payment(amt="10000.00", can_ref="8841", pdate=date(2026, 1, 10), method="CARD")
        s = _make_settlement(gross="10000.00", fee="200.00", net="9800.00", can_ref="8841", sdate=date(2026, 1, 13))

        result = score_candidate(p, s)
        # Ref: 1.0 (0.40) + Amt: 0.95 (0.285) + Date: 0.85 (0.170) + Curr: 1.0 (0.10) = 0.955
        assert result.score_breakdown.total_score >= Decimal("0.9000")

    def test_ranking_multiple_candidates(self):
        p = _make_payment(amt="5000.00", can_ref="2001", pdate=date(2026, 1, 10))
        # Exact candidate
        s_best = _make_settlement(sid="SET_BEST", net="5000.00", can_ref="2001", sdate=date(2026, 1, 10))
        # Noisy candidate
        s_noisy = _make_settlement(sid="SET_NOISY", net="4950.00", can_ref="2001_X", sdate=date(2026, 1, 15))

        ranked = score_and_rank_candidates(p, [s_noisy, s_best])
        assert ranked[0].settlement.settlement_id == "SET_BEST"
        assert ranked[0].score_breakdown.total_score > ranked[1].score_breakdown.total_score
