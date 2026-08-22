"""Deterministic Candidate Generation.

Filters down large settlement datasets to a small list of plausible candidates
for a given payment transaction based on temporal, monetary, and currency constraints.

Rule: Never send raw unbounded datasets to inference or downstream agents.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from .normalizer import NormalizedPayment, NormalizedSettlement


def generate_candidates(
    payment: NormalizedPayment,
    settlements: Sequence[NormalizedSettlement],
    window_days: int = 7,
    amount_tolerance_pct: Decimal = Decimal("0.25"),  # Covers up to 25% fees/holds
    max_candidates: int = 10,
) -> list[NormalizedSettlement]:
    """Find candidate settlement records plausible for the given payment.
    
    Filters:
    1. Temporal window: settlement_date must be between payment_date and payment_date + window_days.
    2. Amount bounds: settlement gross/net within ±amount_tolerance_pct of payment amount.
    3. Excludes cancelled/failed settlement states.
    """
    candidates: list[NormalizedSettlement] = []
    p_amt = payment.amount
    p_date = payment.payment_date

    min_amt = p_amt * (Decimal("1.00") - amount_tolerance_pct)
    max_amt = p_amt * (Decimal("1.00") + amount_tolerance_pct)

    for s in settlements:
        # Check settlement status
        if s.status not in {"SETTLED", "PARTIAL_SETTLED", "PENDING"}:
            continue

        # 1. Date window check
        delta_days = (s.settlement_date - p_date).days
        if not (0 <= delta_days <= window_days):
            continue

        # 2. Amount boundary check (check against both net and gross)
        is_net_in_range = min_amt <= s.net_amount <= max_amt
        is_gross_in_range = min_amt <= s.gross_amount <= max_amt

        if not (is_net_in_range or is_gross_in_range):
            continue

        candidates.append(s)
        if len(candidates) >= max_candidates:
            break

    return candidates
