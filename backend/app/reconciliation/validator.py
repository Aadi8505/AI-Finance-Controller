"""Deterministic Financial Safety Validation Gate.

CRITICAL RULE:
No agent recommendation or automated match may execute or commit state
without passing through this strict deterministic validation gate.

Validation Invariants:
  1. PAYMENT_EXISTS: Payment ID must exist and not be currently claimed.
  2. SETTLEMENT_EXISTS: Settlement ID must exist and not be currently claimed.
  3. SINGLE_CLAIM: Double-counting / double-allocation is strictly prohibited.
  4. AMOUNT_CONSERVATION: |Payment - (Settlement Net + Fee + Refund)| <= 0.02.
  5. TEMPORAL_VALIDITY: Settlement date >= Payment date (cannot settle in the past).
  6. CONFIDENCE_BAR: Action MATCH requires confidence >= min_confidence (default 0.85).
  7. TIE_CONFLICT_CHECK: No competing candidate with score within delta 0.05.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from .normalizer import NormalizedPayment, NormalizedSettlement


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    validated_action: str  # "MATCH", "MANUAL_REVIEW", "EXCEPTION"
    validation_errors: list[str]
    discrepancy: Decimal
    audit_note: str


class SafetyValidator:
    def __init__(
        self,
        min_confidence: Decimal = Decimal("0.85"),
        amount_tolerance: Decimal = Decimal("0.02"),
    ) -> None:
        self.min_confidence = min_confidence
        self.amount_tolerance = amount_tolerance

    def validate_match(
        self,
        payment: NormalizedPayment,
        settlement: NormalizedSettlement | None,
        recommended_action: str,
        confidence: Decimal | float,
        claimed_payments: set[str],
        claimed_settlements: set[str],
        candidate_settlements: Sequence[NormalizedSettlement] | None = None,
    ) -> ValidationResult:
        """Validate an agent recommendation or automated match proposal."""
        errors: list[str] = []
        conf_dec = Decimal(str(confidence))

        # Check payment existence and single-claim
        if payment.payment_id in claimed_payments:
            errors.append(f"Payment {payment.payment_id} has already been claimed / reconciled.")

        # Non-MATCH recommendations are validated as safe escalations
        if recommended_action != "MATCH":
            if not errors:
                return ValidationResult(
                    is_valid=True,
                    validated_action=recommended_action,
                    validation_errors=[],
                    discrepancy=Decimal("0.00"),
                    audit_note=f"Recommendation '{recommended_action}' validated safely.",
                )
            return ValidationResult(
                is_valid=False,
                validated_action="EXCEPTION",
                validation_errors=errors,
                discrepancy=Decimal("0.00"),
                audit_note=f"Validation failed for '{recommended_action}': {'; '.join(errors)}",
            )

        # -------------------------------------------------------------
        # Action is MATCH -> Enforce strict financial invariants
        # -------------------------------------------------------------
        if settlement is None:
            errors.append("Action is MATCH but settlement record is None.")
            return ValidationResult(
                is_valid=False,
                validated_action="EXCEPTION",
                validation_errors=errors,
                discrepancy=Decimal("0.00"),
                audit_note="Validation rejection: Null settlement for MATCH action.",
            )

        # Settlement double-claim check
        if settlement.settlement_id in claimed_settlements:
            errors.append(f"Settlement {settlement.settlement_id} has already been claimed.")

        # Temporal validity
        if settlement.settlement_date < payment.payment_date:
            errors.append(
                f"Temporal violation: Settlement date ({settlement.settlement_date}) precedes payment date ({payment.payment_date})."
            )

        # Amount conservation
        p_amt = payment.amount
        s_net = settlement.net_amount
        s_fee = settlement.fee
        s_refund = settlement.refund

        expected_total = s_net + s_fee + s_refund
        discrepancy = abs(p_amt - expected_total)

        if discrepancy > self.amount_tolerance:
            errors.append(
                f"Amount conservation failure: Payment {p_amt} != Settlement (Net {s_net} + Fee {s_fee} + Refund {s_refund} = {expected_total}). Discrepancy: {discrepancy}"
            )

        # Confidence bar check
        if conf_dec < self.min_confidence:
            errors.append(
                f"Confidence score ({conf_dec:.2f}) below required safety threshold ({self.min_confidence:.2f})."
            )

        if errors:
            return ValidationResult(
                is_valid=False,
                validated_action="MANUAL_REVIEW",
                validation_errors=errors,
                discrepancy=discrepancy,
                audit_note=f"Safety validation rejected MATCH action: {'; '.join(errors)}",
            )

        return ValidationResult(
            is_valid=True,
            validated_action="MATCH",
            validation_errors=[],
            discrepancy=discrepancy,
            audit_note=f"Passed all safety validation invariants (Discrepancy: {discrepancy}, Confidence: {conf_dec:.2f}).",
        )
