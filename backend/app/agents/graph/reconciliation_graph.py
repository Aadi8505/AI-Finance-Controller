"""LangGraph Agent State Machine for Financial Reconciliation Investigation.

Investigates ambiguous medium-confidence financial transactions using tools and
policy retrieval, formulating structured, auditable decisions.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.schemas.decision import AgentDecision, ToolTrace
from app.core.model import query_llm_json
from app.reconciliation.candidates import generate_candidates
from app.reconciliation.normalizer import NormalizedPayment, NormalizedSettlement
from app.reconciliation.scorer import score_and_rank_candidates


class AgentState(TypedDict):
    payment: NormalizedPayment
    settlements: list[NormalizedSettlement]
    candidates: list[dict]
    retrieved_policies: list[dict]
    tool_traces: list[dict]
    decision: AgentDecision | None
    validated: bool
    final_status: str  # "AUTO_RESOLVED", "MANUAL_REVIEW", "EXCEPTION"
    audit_note: str


INVESTIGATION_SYSTEM_PROMPT = """You are an AI Finance Controller for payment reconciliation.
Your role: Investigate ambiguous transactions between payments and settlements.

NON-NEGOTIABLE RULES:
1. NEVER guess or invent amounts.
2. Only recommend "MATCH" if candidate settlement aligns with policy and evidence is unambiguous.
3. If multiple duplicate candidates exist or amounts are unexplained, return "MANUAL_REVIEW".
4. If no candidate can match, return "EXCEPTION".
5. Cite applied policy IDs (e.g. POL_001, POL_002) and provide structured evidence.

Respond ONLY with JSON conforming to:
{
  "payment_id": "...",
  "settlement_id": "..." or null,
  "action": "MATCH" | "MANUAL_REVIEW" | "EXCEPTION",
  "confidence": 0.0-1.0,
  "applied_policy_id": "POL_..." or null,
  "reason_codes": ["..."],
  "evidence_summary": "..."
}"""


def _mock_investigation_logic(user_prompt: str) -> dict:
    """Deterministic offline mock reasoning for LangGraph agent."""
    data = json.loads(user_prompt)
    payment = data["payment"]
    candidates = data["candidates"]

    if not candidates:
        return {
            "payment_id": payment["payment_id"],
            "settlement_id": None,
            "action": "EXCEPTION",
            "confidence": 0.95,
            "applied_policy_id": "POL_005",
            "reason_codes": ["MISSING_SETTLEMENT"],
            "evidence_summary": "Offline agent: No candidate found within valid temporal window.",
        }

    # Check best candidate
    best = candidates[0]
    best_score = float(best["score"])

    # If duplicate high score candidates exist
    if len(candidates) > 1 and abs(best_score - float(candidates[1]["score"])) < 0.05:
        return {
            "payment_id": payment["payment_id"],
            "settlement_id": best["settlement_id"],
            "action": "MANUAL_REVIEW",
            "confidence": 0.65,
            "applied_policy_id": "POL_005",
            "reason_codes": ["AMBIGUOUS_DUPLICATE"],
            "evidence_summary": f"Offline agent: Found 2 conflicting candidates ({best['settlement_id']} vs {candidates[1]['settlement_id']}). Escalating to Human Review.",
        }

    # Check fee scenario (net + fee = payment)
    p_amt = float(payment["amount"])
    s_net = float(best["net_amount"])
    s_fee = float(best["fee"])

    if abs(p_amt - (s_net + s_fee)) < 0.02 and best_score >= 0.85:
        return {
            "payment_id": payment["payment_id"],
            "settlement_id": best["settlement_id"],
            "action": "MATCH",
            "confidence": 0.95,
            "applied_policy_id": "POL_002" if payment["payment_method"] == "UPI" else "POL_003",
            "reason_codes": ["FEE_VERIFIED", "DATE_WINDOW_VALID"],
            "evidence_summary": f"Offline agent: Verified standard {payment['payment_method']} fee of {s_fee} deducted. Total net {s_net} reconciles to gross {p_amt}.",
        }

    # Default to manual review for safety
    return {
        "payment_id": payment["payment_id"],
        "settlement_id": best["settlement_id"],
        "action": "MANUAL_REVIEW",
        "confidence": 0.60,
        "applied_policy_id": "POL_005",
        "reason_codes": ["LOW_CONFIDENCE_AMBIGUITY"],
        "evidence_summary": f"Offline agent: Candidate {best['settlement_id']} has score {best_score:.2f} below definitive match threshold.",
    }


# -----------------------------------------------------------------------------
# Graph Node Definitions
# -----------------------------------------------------------------------------

def node_load_context(state: AgentState) -> dict:
    payment = state["payment"]
    settlements = state["settlements"]

    raw_candidates = generate_candidates(payment, settlements, window_days=7)
    scored = score_and_rank_candidates(payment, raw_candidates)

    formatted_candidates = [
        {
            "settlement_id": sc.settlement.settlement_id,
            "gross_amount": str(sc.settlement.gross_amount),
            "fee": str(sc.settlement.fee),
            "net_amount": str(sc.settlement.net_amount),
            "settlement_date": sc.settlement.settlement_date.isoformat(),
            "score": str(sc.score_breakdown.total_score),
            "reasons": sc.match_reasons,
        }
        for sc in scored
    ]

    return {"candidates": formatted_candidates}


def node_retrieve_policies(state: AgentState) -> dict:
    # Standard policies available to the agent
    policies = [
        {"doc_id": "POL_001", "title": "Settlement Lag Policy", "summary": "Settlement up to T+2 business days standard; T+4 for bank holidays."},
        {"doc_id": "POL_002", "title": "UPI Fee Policy", "summary": "Standard UPI carries 0% under ₹2,000; 0.5%-1.1% merchant interchange."},
        {"doc_id": "POL_003", "title": "Card Fee Policy", "summary": "Domestic cards incur 1.8%-2.2% processing fee."},
        {"doc_id": "POL_005", "title": "Conflict & Ambiguity Policy", "summary": "Conflicting duplicate candidates must escalate to Human Review."},
    ]
    return {"retrieved_policies": policies}


def node_investigate_and_reason(state: AgentState) -> dict:
    payment = state["payment"]
    candidates = state["candidates"]
    policies = state["retrieved_policies"]

    prompt_data = {
        "payment": {
            "payment_id": payment.payment_id,
            "amount": str(payment.amount),
            "payment_date": payment.payment_date.isoformat(),
            "payment_method": payment.payment_method,
            "canonical_reference": payment.canonical_reference,
        },
        "candidates": candidates,
        "policies": policies,
    }

    user_prompt = json.dumps(prompt_data, indent=2)
    raw_decision = query_llm_json(
        system_prompt=INVESTIGATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        mock_response_handler=_mock_investigation_logic,
    )

    try:
        decision = AgentDecision(**raw_decision)
    except Exception:
        decision = AgentDecision(
            payment_id=payment.payment_id,
            action="MANUAL_REVIEW",
            confidence=0.0,
            applied_policy_id="POL_005",
            reason_codes=["SCHEMA_VALIDATION_ERROR"],
            evidence_summary="Failed to parse LLM structured output.",
        )

    return {"decision": decision}


def node_validate_decision(state: AgentState) -> dict:
    decision = state["decision"]
    payment = state["payment"]
    candidates = state["candidates"]

    if decision is None:
        return {"validated": False, "final_status": "EXCEPTION", "audit_note": "No decision formulated."}

    if decision.action == "MATCH":
        if not decision.settlement_id:
            return {"validated": False, "final_status": "EXCEPTION", "audit_note": "Match recommended with null settlement ID."}

        # Check candidate existence
        matching_cands = [c for c in candidates if c["settlement_id"] == decision.settlement_id]
        if not matching_cands:
            return {"validated": False, "final_status": "EXCEPTION", "audit_note": "Recommended settlement not in candidate pool."}

        cand = matching_cands[0]
        # Exact arithmetic balance check: gross = net + fee
        p_amt = Decimal(str(payment.amount))
        s_net = Decimal(cand["net_amount"])
        s_fee = Decimal(cand["fee"])

        if abs(p_amt - (s_net + s_fee)) > Decimal("0.05"):
            return {"validated": False, "final_status": "MANUAL_REVIEW", "audit_note": "Arithmetic balance check failed."}

        return {
            "validated": True,
            "final_status": "AUTO_RESOLVED",
            "audit_note": f"Agent match validated: {decision.evidence_summary} (Policy: {decision.applied_policy_id})",
        }

    elif decision.action == "MANUAL_REVIEW":
        return {
            "validated": True,
            "final_status": "MANUAL_REVIEW",
            "audit_note": f"Routed to Human Review by agent: {decision.evidence_summary}",
        }
    else:
        return {
            "validated": True,
            "final_status": "EXCEPTION",
            "audit_note": f"Exception flagged by agent: {decision.evidence_summary}",
        }


# -----------------------------------------------------------------------------
# Graph Builder
# -----------------------------------------------------------------------------

def build_reconciliation_graph() -> Any:
    workflow = StateGraph(AgentState)

    workflow.add_node("load_context", node_load_context)
    workflow.add_node("retrieve_policies", node_retrieve_policies)
    workflow.add_node("investigate_and_reason", node_investigate_and_reason)
    workflow.add_node("validate_decision", node_validate_decision)

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "retrieve_policies")
    workflow.add_edge("retrieve_policies", "investigate_and_reason")
    workflow.add_edge("investigate_and_reason", "validate_decision")
    workflow.add_edge("validate_decision", END)

    return workflow.compile()


def investigate_payment(
    payment: NormalizedPayment,
    settlements: list[NormalizedSettlement],
) -> AgentState:
    """Run full LangGraph investigation on a single transaction."""
    graph = build_reconciliation_graph()
    initial_state: AgentState = {
        "payment": payment,
        "settlements": settlements,
        "candidates": [],
        "retrieved_policies": [],
        "tool_traces": [],
        "decision": None,
        "validated": False,
        "final_status": "PENDING",
        "audit_note": "",
    }
    result = graph.invoke(initial_state)
    return result
