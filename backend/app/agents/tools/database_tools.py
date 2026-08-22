"""Database lookup tools for the AI Agent."""

from __future__ import annotations

from typing import Any
from app.db.database import get_db_session
from app.models.entities import OrderModel, PaymentModel, SettlementModel
from app.reconciliation.candidates import generate_candidates
from app.reconciliation.normalizer import (
    NormalizedPayment,
    NormalizedSettlement,
    normalize_payment_row,
    normalize_settlement_row,
)
from app.reconciliation.scorer import score_and_rank_candidates


def get_payment_details(payment_id: str) -> dict[str, Any]:
    """Lookup payment record and attached order metadata from database."""
    with get_db_session() as session:
        payment = session.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
        if not payment:
            return {"error": f"Payment {payment_id} not found in database"}

        return {
            "payment_id": payment.payment_id,
            "order_id": payment.order_id,
            "amount": str(payment.amount),
            "payment_date": payment.payment_date.isoformat(),
            "payment_method": payment.payment_method,
            "status": payment.status,
            "raw_reference": payment.raw_reference,
            "canonical_reference": payment.canonical_reference,
            "customer_id": payment.order.customer_id if payment.order else None,
        }


def get_settlement_details(settlement_id: str) -> dict[str, Any]:
    """Lookup settlement record from database."""
    with get_db_session() as session:
        settle = session.query(SettlementModel).filter(SettlementModel.settlement_id == settlement_id).first()
        if not settle:
            return {"error": f"Settlement {settlement_id} not found in database"}

        return {
            "settlement_id": settle.settlement_id,
            "payment_reference": settle.payment_reference,
            "canonical_reference": settle.canonical_reference,
            "gross_amount": str(settle.gross_amount),
            "fee": str(settle.fee),
            "refund": str(settle.refund),
            "net_amount": str(settle.net_amount),
            "settlement_date": settle.settlement_date.isoformat(),
            "status": settle.status,
        }


def query_candidates_db(payment_id: str, window_days: int = 7) -> list[dict[str, Any]]:
    """Query and score plausible settlement candidates from database."""
    with get_db_session() as session:
        payment = session.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
        if not payment:
            return []

        norm_payment = NormalizedPayment(
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            amount=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            status=payment.status,
            raw_reference=payment.raw_reference,
            canonical_reference=payment.canonical_reference,
        )

        all_settlements = session.query(SettlementModel).all()
        norm_settlements = [
            NormalizedSettlement(
                settlement_id=s.settlement_id,
                payment_reference=s.payment_reference,
                canonical_reference=s.canonical_reference,
                gross_amount=s.gross_amount,
                fee=s.fee,
                refund=s.refund,
                net_amount=s.net_amount,
                settlement_date=s.settlement_date,
                status=s.status,
            )
            for s in all_settlements
        ]

        candidates = generate_candidates(norm_payment, norm_settlements, window_days=window_days)
        scored = score_and_rank_candidates(norm_payment, candidates)

        return [
            {
                "settlement_id": sc.settlement.settlement_id,
                "gross_amount": str(sc.settlement.gross_amount),
                "fee": str(sc.settlement.fee),
                "net_amount": str(sc.settlement.net_amount),
                "settlement_date": sc.settlement.settlement_date.isoformat(),
                "score": str(sc.score_breakdown.total_score),
                "routing_tier": sc.routing_tier,
                "match_reasons": sc.match_reasons,
            }
            for sc in scored
        ]
