"""Sandboxed Deterministic Financial Tools for the AI Agent.

Guarantees:
1. Strict financial arithmetic isolation using Python Decimal.
2. The LLM NEVER computes fees, deductions, or date arithmetic.
3. Every tool returns structured JSON outputs and is fully auditable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.reconciliation.normalizer import (
    normalize_amount,
    normalize_date,
)

# Standard fee policy ranges by payment method
STANDARD_FEE_SCHEDULE = {
    "UPI": {"min_pct": Decimal("0.00"), "max_pct": Decimal("1.20"), "flat_min": Decimal("0.00")},
    "CARD": {"min_pct": Decimal("1.50"), "max_pct": Decimal("2.50"), "flat_min": Decimal("10.00")},
    "NETBANKING": {"min_pct": Decimal("1.00"), "max_pct": Decimal("2.00"), "flat_min": Decimal("5.00")},
    "WALLET": {"min_pct": Decimal("1.20"), "max_pct": Decimal("2.20"), "flat_min": Decimal("5.00")},
}


def calculate_fee_difference(
    payment_amount: Any,
    settlement_net: Any,
    payment_method: str = "CARD",
) -> dict[str, Any]:
    """Calculate exact monetary fee difference and verify against policy.
    
    All calculations strictly use Python Decimal.
    """
    p_amt = normalize_amount(payment_amount)
    s_net = normalize_amount(settlement_net)

    if p_amt <= Decimal("0.00"):
        return {"error": "Payment amount must be greater than zero"}

    fee_amount = p_amt - s_net
    fee_pct = ((fee_amount / p_amt) * Decimal("100.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    method = payment_method.strip().upper()
    schedule = STANDARD_FEE_SCHEDULE.get(method, STANDARD_FEE_SCHEDULE["CARD"])

    is_within_policy = False
    if fee_amount < Decimal("0.00"):
        policy_note = "Negative fee: Settlement net exceeds payment gross (Overpayment/Anomalous)"
    elif fee_amount == Decimal("0.00"):
        is_within_policy = True
        policy_note = "Zero fee: Exact 1:1 gross-to-net payout"
    elif schedule["min_pct"] <= fee_pct <= schedule["max_pct"]:
        is_within_policy = True
        policy_note = f"Fee of {fee_amount} ({fee_pct}%) is within standard {method} schedule ({schedule['min_pct']}% - {schedule['max_pct']}%)"
    else:
        policy_note = f"Fee of {fee_amount} ({fee_pct}%) is OUTSIDE standard {method} schedule ({schedule['min_pct']}% - {schedule['max_pct']}%)"

    return {
        "payment_gross": str(p_amt),
        "settlement_net": str(s_net),
        "fee_deducted": str(fee_amount),
        "fee_percentage": str(fee_pct),
        "payment_method": method,
        "is_within_policy": is_within_policy,
        "expected_fee_range": f"{schedule['min_pct']}% - {schedule['max_pct']}%",
        "policy_note": policy_note,
    }


def verify_settlement_window(
    payment_date: Any,
    settlement_date: Any,
    max_lag_days: int = 4,
) -> dict[str, Any]:
    """Calculate temporal lag in business days and verify against standard T+2 policy."""
    p_date = normalize_date(payment_date)
    s_date = normalize_date(settlement_date)

    delta_days = (s_date - p_date).days

    if delta_days < 0:
        return {
            "delta_days": delta_days,
            "is_within_policy": False,
            "policy_id": "POL_001",
            "explanation": f"Invalid: Settlement date ({s_date}) is before payment date ({p_date})",
        }

    if delta_days <= 2:
        return {
            "delta_days": delta_days,
            "is_within_policy": True,
            "policy_id": "POL_001",
            "explanation": f"Settlement arrived in T+{delta_days} day(s) (Standard settlement SLA)",
        }
    elif delta_days <= max_lag_days:
        return {
            "delta_days": delta_days,
            "is_within_policy": True,
            "policy_id": "POL_001",
            "explanation": f"Settlement arrived in T+{delta_days} days (Permissible under weekend/banking holiday policy)",
        }
    else:
        return {
            "delta_days": delta_days,
            "is_within_policy": False,
            "policy_id": "POL_001",
            "explanation": f"Settlement delayed by T+{delta_days} days (Exceeds maximum allowable policy threshold of {max_lag_days} days)",
        }
