"""Unit tests for LangGraph Reconciliation Investigation Agent."""

from datetime import date
from decimal import Decimal
import pytest

from app.agents.graph.reconciliation_graph import (
    build_reconciliation_graph,
    investigate_payment,
)
from app.agents.schemas.decision import AgentDecision
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement


def _make_payment(pid="PAY_101", amt="5000.00", ref="1001", method="CARD") -> NormalizedPayment:
    return NormalizedPayment(
        payment_id=pid,
        order_id="ORD_101",
        amount=Decimal(amt),
        payment_date=date(2026, 1, 10),
        payment_method=method,
        status="SUCCESS",
        raw_reference=ref,
        canonical_reference=ref,
    )


def _make_settlement(sid="SET_201", gross="5000.00", fee="100.00", net="4900.00", ref="1001") -> NormalizedSettlement:
    return NormalizedSettlement(
        settlement_id=sid,
        payment_reference=ref,
        canonical_reference=ref,
        gross_amount=Decimal(gross),
        fee=Decimal(fee),
        refund=Decimal("0.00"),
        net_amount=Decimal(net),
        settlement_date=date(2026, 1, 11),
        status="SETTLED",
    )


def test_build_graph():
    graph = build_reconciliation_graph()
    assert graph is not None


def test_agent_investigate_fee_case():
    payment = _make_payment(amt="5000.00", ref="1001", method="CARD")
    settlement = _make_settlement(sid="SET_CARD_1", gross="5000.00", fee="100.00", net="4900.00", ref="1001")

    result = investigate_payment(payment, [settlement])

    assert result["decision"] is not None
    assert isinstance(result["decision"], AgentDecision)
    assert result["decision"].action == "MATCH"
    assert result["decision"].settlement_id == "SET_CARD_1"
    assert result["validated"] is True
    assert result["final_status"] == "AUTO_RESOLVED"


def test_agent_investigate_missing_case():
    payment = _make_payment(amt="5000.00", ref="9999", method="UPI")
    # No matching settlements
    settlement = _make_settlement(sid="SET_OTHER", gross="12000.00", fee="0.00", net="12000.00", ref="8888")

    result = investigate_payment(payment, [settlement])

    assert result["decision"] is not None
    assert result["decision"].action == "EXCEPTION"
    assert result["final_status"] == "EXCEPTION"


def test_agent_investigate_duplicate_conflict_case():
    payment = _make_payment(amt="5000.00", ref="1001", method="UPI")
    # 2 matching candidates
    s1 = _make_settlement(sid="SET_1", gross="5000.00", fee="0.00", net="5000.00", ref="1001")
    s2 = _make_settlement(sid="SET_2", gross="5000.00", fee="0.00", net="5000.00", ref="1001")

    result = investigate_payment(payment, [s1, s2])

    assert result["decision"] is not None
    assert result["decision"].action == "MANUAL_REVIEW"
    assert result["final_status"] == "MANUAL_REVIEW"
