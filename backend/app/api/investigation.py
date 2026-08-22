"""Agent Investigation API Endpoints."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.graph.reconciliation_graph import investigate_payment
from app.db.database import get_db
from app.models.entities import PaymentModel, SettlementModel
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement

router = APIRouter(prefix="/api/investigate", tags=["AI Investigation Agent"])


@router.post("/{payment_id}")
def run_agent_investigation(payment_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run full LangGraph agent investigation for a specific ambiguous payment."""
    payment = db.query(PaymentModel).filter(PaymentModel.payment_id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found.")

    settlements = db.query(SettlementModel).all()

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
        for s in settlements
    ]

    result = investigate_payment(norm_payment, norm_settlements)

    decision = result.get("decision")
    return {
        "payment_id": payment.payment_id,
        "final_status": result.get("final_status"),
        "validated": result.get("validated"),
        "audit_note": result.get("audit_note"),
        "decision": {
            "action": decision.action if decision else None,
            "confidence": decision.confidence if decision else None,
            "settlement_id": decision.settlement_id if decision else None,
            "applied_policy_id": decision.applied_policy_id if decision else None,
            "reason_codes": decision.reason_codes if decision else [],
            "evidence_summary": decision.evidence_summary if decision else None,
        } if decision else None,
        "candidates": result.get("candidates", []),
        "retrieved_policies": result.get("retrieved_policies", []),
    }
