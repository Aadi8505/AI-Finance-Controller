"""Unit tests for Human Review and Exception Management Service."""

from decimal import Decimal
import pytest
from sqlalchemy import text

from app.db.database import get_db_session, init_db
from app.models.entities import (
    ExceptionModel,
    HumanReviewModel,
    OrderModel,
    PaymentModel,
    ReconciliationResultModel,
    ReconciliationRunModel,
    SettlementModel,
)
from app.services.human_review import HumanReviewService


@pytest.fixture(scope="module", autouse=True)
def setup_review_db():
    init_db()
    with get_db_session() as session:
        # Use raw SQL cascading / ordered cleanup
        session.execute(text("DELETE FROM human_reviews;"))
        session.execute(text("DELETE FROM exceptions;"))
        session.execute(text("DELETE FROM reconciliation_results;"))
        session.execute(text("DELETE FROM reconciliation_runs WHERE run_id='RUN_TEST_001';"))
        session.flush()

        # Create test reconciliation run
        test_run = ReconciliationRunModel(
            run_id="RUN_TEST_001",
            total_processed=10,
            auto_resolved_count=8,
            exception_count=2,
            elapsed_seconds=Decimal("0.05"),
        )
        session.add(test_run)
        session.flush()

        p = session.query(PaymentModel).first()
        if not p:
            pytest.skip("No seeded payments found")

        s = session.query(SettlementModel).first()

        # Create an open exception
        exc = ExceptionModel(
            exception_id="EXC_TEST_001",
            run_id="RUN_TEST_001",
            payment_id=p.payment_id,
            amount=p.amount,
            reason_code="AMBIGUOUS_DUPLICATE",
            severity="MEDIUM",
            description="Testing human review queue",
            candidate_settlement_ids=[s.settlement_id] if s else [],
            suggested_action="HUMAN_REVIEW",
            status="OPEN",
        )
        session.add(exc)


class TestHumanReviewService:
    def test_list_pending_reviews(self):
        service = HumanReviewService()
        reviews = service.list_pending_reviews(status="OPEN")
        assert len(reviews) >= 1
        assert any(r["exception_id"] == "EXC_TEST_001" for r in reviews)

    def test_get_review_detail(self):
        service = HumanReviewService()
        detail = service.get_review_detail("EXC_TEST_001")
        assert detail["exception"]["exception_id"] == "EXC_TEST_001"
        assert detail["payment"] is not None

    def test_reject_match(self):
        service = HumanReviewService()
        res = service.reject_match("EXC_TEST_001", notes="Confirmed spurious")
        assert res["status"] == "SUCCESS"
        assert res["action"] == "REJECT"

        # Verify updated status
        detail = service.get_review_detail("EXC_TEST_001")
        assert detail["exception"]["status"] == "REJECTED"
