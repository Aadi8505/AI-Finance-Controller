"""Reconciliation module package."""
from .candidates import generate_candidates
from .engine import (
    MatchRecord,
    ReconciliationRunResult,
    run_deterministic_reconciliation,
)
from .exceptions import ExceptionReasonCode, ReconciliationException
from .normalizer import (
    NormalizedOrder,
    NormalizedPayment,
    NormalizedSettlement,
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_order_row,
    normalize_payment_row,
    normalize_reference,
    normalize_settlement_row,
)
from .scorer import (
    DEFAULT_T_HIGH,
    DEFAULT_T_LOW,
    ScoreBreakdown,
    ScoredCandidate,
    compute_amount_score,
    compute_date_score,
    compute_reference_similarity,
    score_and_rank_candidates,
    score_candidate,
)
from .validator import SafetyValidator, ValidationResult

__all__ = [
    "NormalizedOrder",
    "NormalizedPayment",
    "NormalizedSettlement",
    "normalize_amount",
    "normalize_currency",
    "normalize_date",
    "normalize_order_row",
    "normalize_payment_row",
    "normalize_reference",
    "normalize_settlement_row",
    "generate_candidates",
    "score_candidate",
    "score_and_rank_candidates",
    "compute_reference_similarity",
    "compute_amount_score",
    "compute_date_score",
    "ScoreBreakdown",
    "ScoredCandidate",
    "DEFAULT_T_HIGH",
    "DEFAULT_T_LOW",
    "ReconciliationException",
    "ExceptionReasonCode",
    "MatchRecord",
    "ReconciliationRunResult",
    "run_deterministic_reconciliation",
    "SafetyValidator",
    "ValidationResult",
]
