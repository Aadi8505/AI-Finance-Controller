"""Deterministic Multi-Factor Scoring & Confidence Routing.

Calculates an empirical match score between a NormalizedPayment and candidate
NormalizedSettlement records using a weighted combination of:
  - Reference similarity (40%)
  - Amount compatibility & fee policies (30%)
  - Temporal / settlement lag window (20%)
  - Currency consistency (10%)

Routes cases into 3 operational buckets:
  - HIGH_CONFIDENCE (Score >= T_high)  -> Auto-resolve
  - MEDIUM_CONFIDENCE (T_low <= Score < T_high) -> Route to Agent Investigation
  - LOW_CONFIDENCE (Score < T_low)     -> Route to Exception Queue
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
import difflib

from .normalizer import NormalizedPayment, NormalizedSettlement

# Default Weights
W_REF = Decimal("0.40")
W_AMT = Decimal("0.30")
W_DATE = Decimal("0.20")
W_CURR = Decimal("0.10")

# Default Confidence Thresholds
DEFAULT_T_HIGH = Decimal("0.90")
DEFAULT_T_LOW = Decimal("0.50")


@dataclass(frozen=True)
class ScoreBreakdown:
    ref_score: Decimal
    amt_score: Decimal
    date_score: Decimal
    curr_score: Decimal
    total_score: Decimal


@dataclass(frozen=True)
class ScoredCandidate:
    settlement: NormalizedSettlement
    score_breakdown: ScoreBreakdown
    routing_tier: str  # "HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"
    match_reasons: list[str]


def compute_reference_similarity(payment_ref: str, settlement_ref: str) -> Decimal:
    """Compute normalized string similarity between canonical reference keys."""
    p = payment_ref.strip()
    s = settlement_ref.strip()

    if not p or not s:
        return Decimal("0.00")

    if p == s:
        return Decimal("1.00")

    # Substring containment
    if p in s or s in p:
        return Decimal("0.90")

    # Sequence matcher ratio
    ratio = difflib.SequenceMatcher(None, p, s).ratio()
    return Decimal(str(round(ratio, 4)))


def compute_amount_score(payment: NormalizedPayment, settlement: NormalizedSettlement) -> tuple[Decimal, list[str]]:
    """Compute compatibility between payment amount and settlement net/gross/fee."""
    reasons = []
    p_amt = payment.amount
    s_net = settlement.net_amount
    s_gross = settlement.gross_amount
    s_fee = settlement.fee

    # Exact penny match with net amount
    if abs(p_amt - s_net) <= Decimal("0.01"):
        reasons.append("Exact 1:1 net amount match")
        return Decimal("1.00"), reasons

    # Exact gross match (with explicit fee deducted)
    if abs(p_amt - s_gross) <= Decimal("0.01") and s_fee > Decimal("0.00"):
        # Check if fee is within normal merchant fee range (0.5% to 3.0%)
        fee_pct = (s_fee / p_amt) * Decimal("100.0")
        if Decimal("0.50") <= fee_pct <= Decimal("3.50"):
            reasons.append(f"Fee of {s_fee} ({fee_pct:.2f}%) matches standard merchant processing policy")
            return Decimal("0.95"), reasons
        else:
            reasons.append(f"Fee of {s_fee} ({fee_pct:.2f}%) exceeds standard fee policy")
            return Decimal("0.75"), reasons

    # Discrepancy check: payment - settlement net
    discrepancy = p_amt - s_net
    if Decimal("0.00") < discrepancy <= (p_amt * Decimal("0.05")):
        reasons.append(f"Small unexplained difference: {discrepancy}")
        return Decimal("0.70"), reasons

    # Partial reserve
    if settlement.status == "PARTIAL_SETTLED" and s_net < p_amt:
        reasons.append(f"Partial settlement: {s_net} vs expected {p_amt}")
        return Decimal("0.60"), reasons

    reasons.append("Unmatched amount difference")
    return Decimal("0.00"), reasons


def compute_date_score(payment: NormalizedPayment, settlement: NormalizedSettlement) -> tuple[Decimal, list[str]]:
    """Score temporal settlement delay."""
    reasons = []
    delta_days = (settlement.settlement_date - payment.payment_date).days

    if delta_days < 0:
        reasons.append(f"Settlement precedes payment date by {abs(delta_days)} days")
        return Decimal("0.00"), reasons

    if delta_days in (0, 1):
        reasons.append(f"Immediate settlement (T+{delta_days})")
        return Decimal("1.00"), reasons
    elif delta_days in (2, 3):
        reasons.append(f"Standard settlement window (T+{delta_days})")
        return Decimal("0.85"), reasons
    elif delta_days in (4, 5):
        reasons.append(f"Delayed settlement (T+{delta_days})")
        return Decimal("0.60"), reasons
    else:
        reasons.append(f"Excessive settlement lag (T+{delta_days})")
        return Decimal("0.20"), reasons


def score_candidate(
    payment: NormalizedPayment,
    settlement: NormalizedSettlement,
    t_high: Decimal = DEFAULT_T_HIGH,
    t_low: Decimal = DEFAULT_T_LOW,
) -> ScoredCandidate:
    """Calculate multi-factor match score for a single candidate."""
    reasons: list[str] = []

    # 1. Reference Score
    ref_score = compute_reference_similarity(
        payment.canonical_reference, settlement.canonical_reference
    )
    if ref_score == Decimal("1.00"):
        reasons.append("Canonical reference keys match exactly")
    elif ref_score >= Decimal("0.80"):
        reasons.append(f"High reference similarity ({ref_score})")

    # 2. Amount Score
    amt_score, amt_reasons = compute_amount_score(payment, settlement)
    reasons.extend(amt_reasons)

    # 3. Date Score
    date_score, date_reasons = compute_date_score(payment, settlement)
    reasons.extend(date_reasons)

    # 4. Currency Score (Standardized INR default)
    curr_score = Decimal("1.00")

    # Total Weighted Score
    total_score = (
        (W_REF * ref_score)
        + (W_AMT * amt_score)
        + (W_DATE * date_score)
        + (W_CURR * curr_score)
    ).quantize(Decimal("0.0001"))

    # Confidence Routing
    if total_score >= t_high:
        tier = "HIGH_CONFIDENCE"
    elif total_score >= t_low:
        tier = "MEDIUM_CONFIDENCE"
    else:
        tier = "LOW_CONFIDENCE"

    breakdown = ScoreBreakdown(
        ref_score=ref_score,
        amt_score=amt_score,
        date_score=date_score,
        curr_score=curr_score,
        total_score=total_score,
    )

    return ScoredCandidate(
        settlement=settlement,
        score_breakdown=breakdown,
        routing_tier=tier,
        match_reasons=reasons,
    )


def score_and_rank_candidates(
    payment: NormalizedPayment,
    candidates: Sequence[NormalizedSettlement],
    t_high: Decimal = DEFAULT_T_HIGH,
    t_low: Decimal = DEFAULT_T_LOW,
) -> list[ScoredCandidate]:
    """Score all candidates and return them sorted descending by match score."""
    scored = [
        score_candidate(payment, c, t_high=t_high, t_low=t_low)
        for c in candidates
    ]
    scored.sort(key=lambda s: s.score_breakdown.total_score, reverse=True)
    return scored
