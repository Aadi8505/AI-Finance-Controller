"""Human-in-the-Loop Review & Exception Management Service.

Provides finance operators with structured workflows to inspect ambiguous
transactions, review AI recommendations and cited policies, and execute
auditable human overrides (Approve, Reject, Escalate).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.db.database import get_db_session
from app.models.entities import (
    ExceptionModel,
    HumanReviewModel,
    PaymentModel,
    ReconciliationResultModel,
    SettlementModel,
)
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement
from app.reconciliation.validator import SafetyValidator


class HumanReviewService:
    def __init__(self) -> None:
        self.validator = SafetyValidator()

    def list_pending_reviews(
        self,
        status: str = "OPEN",
        reason_code: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch active review items with metadata and candidate details."""
        with get_db_session() as session:
            query = session.query(ExceptionModel).filter(ExceptionModel.status == status)
            if reason_code:
                query = query.filter(ExceptionModel.reason_code == reason_code)

            exceptions = query.order_by(ExceptionModel.created_at.desc()).offset(offset).limit(limit).all()

            results = []
            for exc in exceptions:
                results.append({
                    "exception_id": exc.exception_id,
                    "payment_id": exc.payment_id,
                    "amount": str(exc.amount),
                    "reason_code": exc.reason_code,
                    "severity": exc.severity,
                    "description": exc.description,
                    "candidate_settlement_ids": exc.candidate_settlement_ids or [],
                    "suggested_action": exc.suggested_action,
                    "status": exc.status,
                    "metadata": exc.metadata_json or {},
                    "created_at": exc.created_at.isoformat() if exc.created_at else None,
                })
            return results

    def get_review_detail(self, exception_id: str) -> dict[str, Any]:
        """Fetch comprehensive transaction detail for human decision-making."""
        with get_db_session() as session:
            exc = session.query(ExceptionModel).filter(ExceptionModel.exception_id == exception_id).first()
            if not exc:
                raise ValueError(f"Exception {exception_id} not found.")

            payment = session.query(PaymentModel).filter(PaymentModel.payment_id == exc.payment_id).first()
            candidates = []
            if exc.candidate_settlement_ids:
                settlements = (
                    session.query(SettlementModel)
                    .filter(SettlementModel.settlement_id.in_(exc.candidate_settlement_ids))
                    .all()
                )
                for s in settlements:
                    candidates.append({
                        "settlement_id": s.settlement_id,
                        "payment_reference": s.payment_reference,
                        "canonical_reference": s.canonical_reference,
                        "gross_amount": str(s.gross_amount),
                        "fee": str(s.fee),
                        "refund": str(s.refund),
                        "net_amount": str(s.net_amount),
                        "settlement_date": s.settlement_date.isoformat(),
                        "status": s.status,
                    })

            return {
                "exception": {
                    "exception_id": exc.exception_id,
                    "reason_code": exc.reason_code,
                    "severity": exc.severity,
                    "description": exc.description,
                    "status": exc.status,
                },
                "payment": {
                    "payment_id": payment.payment_id,
                    "order_id": payment.order_id,
                    "amount": str(payment.amount),
                    "payment_date": payment.payment_date.isoformat(),
                    "payment_method": payment.payment_method,
                    "raw_reference": payment.raw_reference,
                    "canonical_reference": payment.canonical_reference,
                } if payment else None,
                "candidates": candidates,
            }

    def approve_match(
        self,
        exception_id: str,
        settlement_id: str,
        reviewer_id: str = "FIN_OPERATOR_01",
        notes: str = "Approved after human review.",
        allow_discrepancy_adjustment: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Human operator manual match approval with safety validation and audit log."""
        with get_db_session() as session:
            exc = session.query(ExceptionModel).filter(ExceptionModel.exception_id == exception_id).first()
            if not exc:
                raise ValueError(f"Exception {exception_id} not found.")

            payment = session.query(PaymentModel).filter(PaymentModel.payment_id == exc.payment_id).first()
            settle = session.query(SettlementModel).filter(SettlementModel.settlement_id == settlement_id).first()

            if not payment or not settle:
                raise ValueError("Payment or Settlement record not found.")

            effective_fee = settle.fee
            if allow_discrepancy_adjustment and (payment.amount > (settle.net_amount + settle.fee)):
                # Attribute difference to gateway fee or reserve holdback (POL_006)
                effective_fee = payment.amount - settle.net_amount

            # Safety validation
            norm_p = NormalizedPayment(
                payment_id=payment.payment_id,
                order_id=payment.order_id,
                amount=payment.amount,
                payment_date=payment.payment_date,
                payment_method=payment.payment_method,
                status=payment.status,
                raw_reference=payment.raw_reference,
                canonical_reference=payment.canonical_reference,
            )
            norm_s = NormalizedSettlement(
                settlement_id=settle.settlement_id,
                payment_reference=settle.payment_reference,
                canonical_reference=settle.canonical_reference,
                gross_amount=settle.gross_amount,
                fee=effective_fee,
                refund=settle.refund,
                net_amount=settle.net_amount,
                settlement_date=settle.settlement_date,
                status=settle.status,
            )

            # Enforce single claim from DB
            claimed_s = {
                r[0] for r in session.query(ReconciliationResultModel.settlement_id).all()
            }
            claimed_p = {
                r[0] for r in session.query(ReconciliationResultModel.payment_id).all()
            }

            val_res = self.validator.validate_match(
                payment=norm_p,
                settlement=norm_s,
                recommended_action="MATCH",
                confidence=1.00,
                claimed_payments=claimed_p,
                claimed_settlements=claimed_s,
            )

            if not val_res.is_valid:
                raise ValueError(f"Human match approval rejected by safety validator: {'; '.join(val_res.validation_errors)}")

            # Create Reconciliation Result
            discrepancy = payment.amount - (settle.net_amount + effective_fee)
            rec_result = ReconciliationResultModel(
                run_id=exc.run_id or f"RUN_{uuid.uuid4().hex[:8].upper()}",
                payment_id=payment.payment_id,
                settlement_id=settle.settlement_id,
                amount_paid=payment.amount,
                settlement_net=settle.net_amount,
                fee_deducted=effective_fee,
                discrepancy=discrepancy,
                confidence_score=Decimal("1.0000"),
                status="MANUALLY_RECONCILED",
                audit_note=f"Operator {reviewer_id} approved match (Holdback/Fee: ₹{effective_fee}). Note: {notes}",
            )
            session.add(rec_result)

            # Update exception status
            exc.status = "RESOLVED"

            # Create audit record
            audit = HumanReviewModel(
                review_id=f"REV_{uuid.uuid4().hex[:6].upper()}",
                exception_id=exc.exception_id,
                reviewer_id=reviewer_id,
                action="APPROVE_MATCH",
                notes=notes,
            )
            session.add(audit)

            return {
                "status": "SUCCESS",
                "action": "APPROVE_MATCH",
                "payment_id": payment.payment_id,
                "settlement_id": settle.settlement_id,
                "audit_note": rec_result.audit_note,
            }

    def reject_match(
        self,
        exception_id: str,
        reviewer_id: str = "FIN_OPERATOR_01",
        notes: str = "Rejected - Confirmed missing payout.",
    ) -> dict[str, Any]:
        """Operator explicitly rejects match and records audit log."""
        with get_db_session() as session:
            exc = session.query(ExceptionModel).filter(ExceptionModel.exception_id == exception_id).first()
            if not exc:
                raise ValueError(f"Exception {exception_id} not found.")

            exc.status = "REJECTED"

            audit = HumanReviewModel(
                review_id=f"REV_{uuid.uuid4().hex[:6].upper()}",
                exception_id=exc.exception_id,
                reviewer_id=reviewer_id,
                action="REJECT",
                notes=notes,
            )
            session.add(audit)

            return {
                "status": "SUCCESS",
                "action": "REJECT",
                "exception_id": exc.exception_id,
                "notes": notes,
            }
