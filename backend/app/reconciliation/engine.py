"""Deterministic Reconciliation Engine (Baseline).

Processes normalized payment records against settlement records using candidate
generation, multi-factor scoring, single-claim settlement allocation, and
confidence routing without invoking LLMs.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .candidates import generate_candidates
from .exceptions import ExceptionReasonCode, ReconciliationException
from .normalizer import NormalizedPayment, NormalizedSettlement
from .scorer import (
    DEFAULT_T_HIGH,
    DEFAULT_T_LOW,
    ScoreBreakdown,
    score_and_rank_candidates,
)


@dataclass(frozen=True)
class MatchRecord:
    payment_id: str
    settlement_id: str
    amount_paid: Decimal
    settlement_net: Decimal
    fee_deducted: Decimal
    discrepancy: Decimal  # amount_paid - (settlement_net + fee_deducted)
    confidence_score: Decimal
    score_breakdown: ScoreBreakdown
    status: str  # "MATCHED", "AUTO_RESOLVED"
    audit_note: str


@dataclass
class ReconciliationRunResult:
    run_id: str
    total_processed: int
    matched: list[MatchRecord]
    exceptions: list[ReconciliationException]
    elapsed_seconds: float
    claimed_settlements: set[str]

    @property
    def auto_resolved_count(self) -> int:
        return len(self.matched)

    @property
    def exception_count(self) -> int:
        return len(self.exceptions)

    @property
    def throughput_per_second(self) -> float:
        return round(self.total_processed / max(self.elapsed_seconds, 0.001), 2)


def run_deterministic_reconciliation(
    payments: Sequence[NormalizedPayment],
    settlements: Sequence[NormalizedSettlement],
    t_high: Decimal = DEFAULT_T_HIGH,
    t_low: Decimal = DEFAULT_T_LOW,
    window_days: int = 7,
    run_id: str | None = None,
) -> ReconciliationRunResult:
    """Execute rule-based deterministic reconciliation pass across all payments.
    
    1. For each payment, prune settlements down to candidate list.
    2. Score and rank candidates using multi-factor weights.
    3. If best candidate score >= t_high and settlement unallocated -> Auto-resolve & Claim.
    4. If score is ambiguous or low -> Emit specific Exception record.
    """
    start_time = time.perf_counter()
    run_id = run_id or f"RUN_{uuid.uuid4().hex[:8].upper()}"

    matched: list[MatchRecord] = []
    exceptions: list[ReconciliationException] = []
    claimed_settlements: set[str] = set()

    # Pre-index settlements available
    settlement_map = {s.settlement_id: s for s in settlements}

    for payment in payments:
        # Filter available (unclaimed) candidates
        avail_settlements = [
            s for s in settlements if s.settlement_id not in claimed_settlements
        ]

        candidates = generate_candidates(payment, avail_settlements, window_days=window_days)

        if not candidates:
            # No candidate found in window/amount bounds
            exceptions.append(
                ReconciliationException(
                    exception_id=f"EXC_{uuid.uuid4().hex[:6].upper()}",
                    payment_id=payment.payment_id,
                    amount=payment.amount,
                    reason_code=ExceptionReasonCode.MISSING_SETTLEMENT,
                    severity="HIGH",
                    description=f"No settlement found within {window_days} days date window and ±25% amount tolerance",
                    candidate_settlement_ids=[],
                    suggested_action="INVESTIGATE_AGENT",
                    metadata={"canonical_reference": payment.canonical_reference},
                )
            )
            continue

        scored_candidates = score_and_rank_candidates(
            payment, candidates, t_high=t_high, t_low=t_low
        )
        best = scored_candidates[0]
        best_settle = best.settlement
        best_score = best.score_breakdown.total_score

        # Check for ambiguous tie (two candidates with near-identical high score)
        if len(scored_candidates) > 1:
            second_best = scored_candidates[1]
            diff = best_score - second_best.score_breakdown.total_score
            if diff < Decimal("0.05") and best_score >= t_low:
                exceptions.append(
                    ReconciliationException(
                        exception_id=f"EXC_{uuid.uuid4().hex[:6].upper()}",
                        payment_id=payment.payment_id,
                        amount=payment.amount,
                        reason_code=ExceptionReasonCode.AMBIGUOUS_DUPLICATE,
                        severity="MEDIUM",
                        description=f"Conflicting settlement candidates found: {best_settle.settlement_id} ({best_score}) vs {second_best.settlement.settlement_id} ({second_best.score_breakdown.total_score})",
                        candidate_settlement_ids=[c.settlement.settlement_id for c in scored_candidates[:3]],
                        suggested_action="HUMAN_REVIEW",
                        metadata={"best_score": str(best_score), "second_score": str(second_best.score_breakdown.total_score)},
                    )
                )
                continue

        # Check if candidate is high confidence
        if best.routing_tier == "HIGH_CONFIDENCE":
            claimed_settlements.add(best_settle.settlement_id)
            discrepancy = payment.amount - (best_settle.net_amount + best_settle.fee)

            matched.append(
                MatchRecord(
                    payment_id=payment.payment_id,
                    settlement_id=best_settle.settlement_id,
                    amount_paid=payment.amount,
                    settlement_net=best_settle.net_amount,
                    fee_deducted=best_settle.fee,
                    discrepancy=discrepancy,
                    confidence_score=best_score,
                    score_breakdown=best.score_breakdown,
                    status="AUTO_RESOLVED",
                    audit_note="; ".join(best.match_reasons),
                )
            )
        elif best_settle.status == "PARTIAL_SETTLED":
            exceptions.append(
                ReconciliationException(
                    exception_id=f"EXC_{uuid.uuid4().hex[:6].upper()}",
                    payment_id=payment.payment_id,
                    amount=payment.amount,
                    reason_code=ExceptionReasonCode.PARTIAL_SETTLEMENT,
                    severity="LOW",
                    description=f"Settlement {best_settle.settlement_id} is partially settled (Net: {best_settle.net_amount} vs Expected: {payment.amount})",
                    candidate_settlement_ids=[best_settle.settlement_id],
                    suggested_action="HUMAN_REVIEW",
                    metadata={"partial_net": str(best_settle.net_amount)},
                )
            )
        else:
            # Medium or low confidence exception
            reason_code = (
                ExceptionReasonCode.UNMATCHED_AMOUNT
                if best.score_breakdown.amt_score < Decimal("0.80")
                else ExceptionReasonCode.LOW_CONFIDENCE
            )
            exceptions.append(
                ReconciliationException(
                    exception_id=f"EXC_{uuid.uuid4().hex[:6].upper()}",
                    payment_id=payment.payment_id,
                    amount=payment.amount,
                    reason_code=reason_code,
                    severity="MEDIUM",
                    description=f"Candidate {best_settle.settlement_id} confidence score ({best_score}) below auto-resolve threshold ({t_high})",
                    candidate_settlement_ids=[best_settle.settlement_id],
                    suggested_action="INVESTIGATE_AGENT",
                    metadata={"score": str(best_score), "reasons": best.match_reasons},
                )
            )

    elapsed = time.perf_counter() - start_time

    return ReconciliationRunResult(
        run_id=run_id,
        total_processed=len(payments),
        matched=matched,
        exceptions=exceptions,
        elapsed_seconds=elapsed,
        claimed_settlements=claimed_settlements,
    )
