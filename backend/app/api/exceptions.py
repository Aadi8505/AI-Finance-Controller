"""Exception and Human Review API Endpoints."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.human_review import HumanReviewService

router = APIRouter(prefix="/api/exceptions", tags=["Exceptions & Review"])
review_service = HumanReviewService()


class ApprovalRequest(BaseModel):
    settlement_id: str
    reviewer_id: str = "FIN_OPERATOR_01"
    notes: str = "Manual approval via operator API"


class RejectionRequest(BaseModel):
    reviewer_id: str = "FIN_OPERATOR_01"
    notes: str = "Manual rejection via operator API"


@router.get("")
def list_exceptions(
    status: str = "OPEN",
    reason_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List exceptions filtered by review status and reason code."""
    return review_service.list_pending_reviews(
        status=status, reason_code=reason_code, limit=limit, offset=offset
    )


@router.get("/{exception_id}")
def get_exception_detail(exception_id: str) -> dict[str, Any]:
    """Get full exception detail, payment data, and candidate settlement options."""
    try:
        return review_service.get_review_detail(exception_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{exception_id}/approve")
def approve_exception(exception_id: str, req: ApprovalRequest) -> dict[str, Any]:
    """Approve a proposed match for an ambiguous exception."""
    try:
        return review_service.approve_match(
            exception_id=exception_id,
            settlement_id=req.settlement_id,
            reviewer_id=req.reviewer_id,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{exception_id}/reject")
def reject_exception(exception_id: str, req: RejectionRequest) -> dict[str, Any]:
    """Reject an exception, marking it as confirmed unallocated."""
    try:
        return review_service.reject_match(
            exception_id=exception_id,
            reviewer_id=req.reviewer_id,
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
