"""Standardized Financial Exception Taxonomy & Data Structures.

Every unresolved or ambiguous transaction produces an explicit, auditable
exception object with structured reason codes.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class ExceptionReasonCode:
    UNMATCHED_AMOUNT = "UNMATCHED_AMOUNT"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    AMBIGUOUS_DUPLICATE = "AMBIGUOUS_DUPLICATE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    PARTIAL_SETTLEMENT = "PARTIAL_SETTLEMENT"
    EXCESSIVE_DELAY = "EXCESSIVE_DELAY"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass(frozen=True)
class ReconciliationException:
    exception_id: str
    payment_id: str
    amount: Decimal
    reason_code: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    description: str
    candidate_settlement_ids: list[str]
    suggested_action: str  # "HUMAN_REVIEW", "INVESTIGATE_AGENT", "MANUAL_ENTRY"
    metadata: dict[str, Any]
