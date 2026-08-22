"""Structured Pydantic Schemas for Agent Decisions and Tool Invocations."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    payment_id: str = Field(description="Unique identifier of the payment investigated")
    settlement_id: Optional[str] = Field(None, description="Matching settlement ID if match resolved, else None")
    action: Literal["MATCH", "MANUAL_REVIEW", "EXCEPTION"] = Field(
        description="Recommended action: MATCH (resolve), MANUAL_REVIEW (escalate to human), EXCEPTION (flag error)"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    applied_policy_id: Optional[str] = Field(None, description="Doc ID of policy applied (e.g. POL_001)")
    reason_codes: list[str] = Field(default_factory=list, description="Reason codes supporting decision")
    evidence_summary: str = Field(description="Human-readable audit rationale citing tools and policy facts")


class ToolTrace(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
    tool_result: dict[str, Any]
    execution_time_ms: float
