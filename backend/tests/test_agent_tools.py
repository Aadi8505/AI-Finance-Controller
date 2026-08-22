"""Unit tests for Sandboxed Agent Tools and Tool Registry."""

from decimal import Decimal
import pytest

from app.agents.tools.financial_tools import calculate_fee_difference, verify_settlement_window
from app.agents.tools.registry import OPENAI_TOOLS_SCHEMAS, TOOLS_REGISTRY, dispatch_tool_call
from app.agents.tools.database_tools import get_payment_details, get_settlement_details, query_candidates_db
from app.db.database import init_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()


class TestFinancialTools:
    def test_fee_calculator_card_valid(self):
        res = calculate_fee_difference(payment_amount="5000.00", settlement_net="4900.00", payment_method="CARD")
        assert res["fee_deducted"] == "100.00"
        assert res["fee_percentage"] == "2.00"
        assert res["is_within_policy"] is True

    def test_fee_calculator_upi_zero(self):
        res = calculate_fee_difference(payment_amount="2000.00", settlement_net="2000.00", payment_method="UPI")
        assert res["fee_deducted"] == "0.00"
        assert res["fee_percentage"] == "0.00"
        assert res["is_within_policy"] is True

    def test_fee_calculator_excessive(self):
        res = calculate_fee_difference(payment_amount="1000.00", settlement_net="800.00", payment_method="UPI")
        assert res["fee_percentage"] == "20.00"
        assert res["is_within_policy"] is False

    def test_date_window_immediate(self):
        res = verify_settlement_window("2026-01-10", "2026-01-11")
        assert res["delta_days"] == 1
        assert res["is_within_policy"] is True

    def test_date_window_excessive_delay(self):
        res = verify_settlement_window("2026-01-10", "2026-01-20")
        assert res["delta_days"] == 10
        assert res["is_within_policy"] is False


class TestToolRegistryAndDispatcher:
    def test_registered_schemas(self):
        names = [s["function"]["name"] for s in OPENAI_TOOLS_SCHEMAS]
        assert "calculate_fee_difference" in names
        assert "verify_settlement_window" in names
        assert "get_payment_details" in names

    def test_dispatch_financial_tool(self):
        res, trace = dispatch_tool_call(
            "calculate_fee_difference",
            {"payment_amount": "10000.00", "settlement_net": "9800.00", "payment_method": "CARD"},
        )
        assert res["fee_deducted"] == "200.00"
        assert trace.tool_name == "calculate_fee_difference"
        assert trace.execution_time_ms >= 0.0

    def test_dispatch_database_tool(self):
        res, trace = dispatch_tool_call("get_payment_details", {"payment_id": "PAY_5001"})
        assert trace.tool_name == "get_payment_details"
        if "error" not in res:
            assert res["payment_id"] == "PAY_5001"
