"""Tool Registry, OpenAI Function Schemas, and Execution Dispatcher."""

from __future__ import annotations

import time
from typing import Any, Callable

from app.agents.schemas.decision import ToolTrace
from app.rag.retriever import search_policies
from .database_tools import get_payment_details, get_settlement_details, query_candidates_db
from .financial_tools import calculate_fee_difference, verify_settlement_window

TOOLS_REGISTRY: dict[str, Callable[..., Any]] = {
    "get_payment_details": get_payment_details,
    "get_settlement_details": get_settlement_details,
    "query_candidates_db": query_candidates_db,
    "calculate_fee_difference": calculate_fee_difference,
    "verify_settlement_window": verify_settlement_window,
    "search_policies": search_policies,
}

OPENAI_TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_payment_details",
            "description": "Fetch detailed metadata for a payment ID including customer, date, method, and reference.",
            "parameters": {
                "type": "object",
                "properties": {"payment_id": {"type": "string", "description": "The payment identifier, e.g. PAY_5001"}},
                "required": ["payment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_settlement_details",
            "description": "Fetch detailed payout metadata for a settlement ID including net amount, fee, and payout date.",
            "parameters": {
                "type": "object",
                "properties": {"settlement_id": {"type": "string", "description": "The settlement identifier, e.g. SET_9001"}},
                "required": ["settlement_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_candidates_db",
            "description": "Find and rank candidate settlement records from the database for a given payment ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {"type": "string", "description": "The payment identifier"},
                    "window_days": {"type": "integer", "default": 7, "description": "Maximum days between payment and settlement"},
                },
                "required": ["payment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_fee_difference",
            "description": "Calculate exact monetary difference between payment and settlement using pure Decimal arithmetic, and check against merchant policy schedule.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_amount": {"type": "string", "description": "Payment gross amount, e.g. 5000.00"},
                    "settlement_net": {"type": "string", "description": "Settlement net amount, e.g. 4900.00"},
                    "payment_method": {"type": "string", "enum": ["UPI", "CARD", "NETBANKING", "WALLET"], "description": "Payment method"},
                },
                "required": ["payment_amount", "settlement_net", "payment_method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_settlement_window",
            "description": "Compute settlement delay lag in business days and verify against standard T+2 policy SLA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_date": {"type": "string", "description": "Payment date YYYY-MM-DD"},
                    "settlement_date": {"type": "string", "description": "Settlement payout date YYYY-MM-DD"},
                },
                "required": ["payment_date", "settlement_date"],
            },
        },
    },
]


def dispatch_tool_call(tool_name: str, tool_args: dict[str, Any]) -> tuple[dict[str, Any], ToolTrace]:
    """Execute a registered tool and record an immutable, timed ToolTrace."""
    if tool_name not in TOOLS_REGISTRY:
        error_res = {"error": f"Tool '{tool_name}' is not registered"}
        return error_res, ToolTrace(tool_name=tool_name, tool_args=tool_args, tool_result=error_res, execution_time_ms=0.0)

    start = time.perf_counter()
    try:
        result = TOOLS_REGISTRY[tool_name](**tool_args)
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        trace = ToolTrace(
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=result if isinstance(result, dict) else {"data": result},
            execution_time_ms=elapsed_ms,
        )
        return result, trace
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        err_dict = {"error": f"Tool execution failed: {str(e)}"}
        return err_dict, ToolTrace(tool_name=tool_name, tool_args=tool_args, tool_result=err_dict, execution_time_ms=elapsed_ms)
