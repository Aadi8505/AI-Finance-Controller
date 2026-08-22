"""Unit tests for deterministic normalization functions."""

from datetime import date
from decimal import Decimal

import pytest

from app.reconciliation.normalizer import (
    normalize_amount,
    normalize_currency,
    normalize_date,
    normalize_order_row,
    normalize_payment_row,
    normalize_reference,
    normalize_settlement_row,
)


class TestReferenceNormalization:
    def test_clean_reference(self):
        assert normalize_reference("RZP_REF_1001") == "1001"
        assert normalize_reference("RZP-REF-1002") == "1002"
        assert normalize_reference("RZP/REF/1003") == "1003"
        assert normalize_reference("rzp_ref_1004") == "1004"
        assert normalize_reference(" RZP REF 1005 ") == "1005"

    def test_various_prefixes(self):
        assert normalize_reference("ORD_5001") == "5001"
        assert normalize_reference("PAY-9912") == "9912"
        assert normalize_reference("TXN_ABC88") == "ABC88"
        assert normalize_reference("REF12345") == "12345"

    def test_edge_cases(self):
        assert normalize_reference("") == ""
        assert normalize_reference(None) == ""
        assert normalize_reference("   ") == ""
        assert normalize_reference("ORDER-XYZ-999") == "XYZ999"


class TestDateNormalization:
    def test_iso_format(self):
        assert normalize_date("2026-02-08") == date(2026, 2, 8)

    def test_indian_format(self):
        assert normalize_date("08/02/2026") == date(2026, 2, 8)
        assert normalize_date("28-01-2026") == date(2026, 1, 28)

    def test_existing_date(self):
        d = date(2026, 3, 15)
        assert normalize_date(d) == d

    def test_invalid_date(self):
        with pytest.raises(ValueError):
            normalize_date("invalid-date-string")


class TestAmountNormalization:
    def test_plain_numbers(self):
        assert normalize_amount(5000) == Decimal("5000.00")
        assert normalize_amount(25.5) == Decimal("25.50")
        assert normalize_amount("4975") == Decimal("4975.00")

    def test_currency_symbols_and_commas(self):
        assert normalize_amount("₹5,000.00") == Decimal("5000.00")
        assert normalize_amount("₹ 26,964.50") == Decimal("26964.50")
        assert normalize_amount("$1,234.56") == Decimal("1234.56")
        assert normalize_amount("€100.00") == Decimal("100.00")

    def test_signed_amounts(self):
        assert normalize_amount("-50.25") == Decimal("-50.25")
        assert normalize_amount("-₹1,000.00") == Decimal("-1000.00")

    def test_invalid_amount(self):
        with pytest.raises(ValueError):
            normalize_amount("not_a_number")


class TestCurrencyNormalization:
    def test_symbols(self):
        assert normalize_currency("₹") == "INR"
        assert normalize_currency("Rs") == "INR"
        assert normalize_currency("Rs.") == "INR"
        assert normalize_currency("$") == "USD"
        assert normalize_currency("€") == "EUR"
        assert normalize_currency("£") == "GBP"

    def test_iso_codes(self):
        assert normalize_currency("INR") == "INR"
        assert normalize_currency("inr") == "INR"
        assert normalize_currency("usd") == "USD"


class TestRecordRowNormalization:
    def test_payment_row(self):
        row = {
            "payment_id": "PAY_5001",
            "order_id": "ORD_1001",
            "amount": "₹7,304.00",
            "payment_date": "08/02/2026",
            "payment_method": "upi",
            "status": "success",
            "reference": "RZP/REF/1001",
        }
        norm = normalize_payment_row(row)
        assert norm.payment_id == "PAY_5001"
        assert norm.amount == Decimal("7304.00")
        assert norm.payment_date == date(2026, 2, 8)
        assert norm.canonical_reference == "1001"
        assert norm.payment_method == "UPI"

    def test_settlement_row(self):
        row = {
            "settlement_id": "SET_9001",
            "payment_reference": "RZP-REF-1001",
            "gross_amount": "7304.00",
            "fee": "100.00",
            "refund": "0.00",
            "net_amount": "7204.00",
            "settlement_date": "2026-02-09",
            "status": "settled",
        }
        norm = normalize_settlement_row(row)
        assert norm.settlement_id == "SET_9001"
        assert norm.canonical_reference == "1001"
        assert norm.gross_amount == Decimal("7304.00")
        assert norm.fee == Decimal("100.00")
        assert norm.net_amount == Decimal("7204.00")
        assert norm.settlement_date == date(2026, 2, 9)

    def test_order_row(self):
        row = {
            "order_id": "ORD_1001",
            "customer_id": "CUST_001",
            "amount": "₹5,000.00",
            "currency": "₹",
            "order_date": "2026-02-08",
            "status": "paid",
        }
        norm = normalize_order_row(row)
        assert norm.order_id == "ORD_1001"
        assert norm.amount == Decimal("5000.00")
        assert norm.currency == "INR"
