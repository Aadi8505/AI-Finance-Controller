"""Deterministic Normalization & Data Preprocessing Layer.

Performs robust parsing, cleaning, and canonicalization of financial records
WITHOUT calling an LLM.

Handles:
- Reference ID normalization (delimiters, casing, whitespace, prefixes)
- Date parsing across ISO, Indian (DD/MM/YYYY), and US (MM/DD/YYYY) formats
- Monetary parsing into exact Decimal representations (currency symbols, commas)
- Currency canonicalization
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


@dataclass(frozen=True)
class NormalizedPayment:
    payment_id: str
    order_id: str
    amount: Decimal
    payment_date: date
    payment_method: str
    status: str
    raw_reference: str
    canonical_reference: str


@dataclass(frozen=True)
class NormalizedSettlement:
    settlement_id: str
    payment_reference: str
    canonical_reference: str
    gross_amount: Decimal
    fee: Decimal
    refund: Decimal
    net_amount: Decimal
    settlement_date: date
    status: str


@dataclass(frozen=True)
class NormalizedOrder:
    order_id: str
    customer_id: str
    amount: Decimal
    currency: str
    order_date: date
    status: str


def normalize_reference(raw_ref: str | None) -> str:
    """Normalize a payment or settlement reference key into a canonical string.
    
    Examples:
        'RZP-REF-1008'   -> '1008'
        'RZP/REF/1008'   -> '1008'
        'rzp_ref_1008'   -> '1008'
        ' RZP REF 1008 ' -> '1008'
        'ORD1008'        -> '1008'
        'REF12345'       -> '12345'
        'ORDER-XYZ-999'  -> 'XYZ999'
        'TXN_ABC88'      -> 'ABC88'
    """
    if not raw_ref:
        return ""
    
    # 1. Clean whitespace & uppercase
    s = str(raw_ref).strip().upper()
    
    # 2. Replace separators with spaces
    s_clean = re.sub(r"[-_/\\:]+", " ", s)
    
    # 3. Strip standalone common prefixes
    prefixes = {"RZP", "REF", "ORD", "ORDER", "PAY", "PAYMENT", "TXN", "TRANS"}
    tokens = [t for t in s_clean.split() if t not in prefixes]
    
    # 4. If tokens exist, check if leading token has attached prefix (e.g. REF12345 -> 12345)
    cleaned_tokens = []
    for t in tokens:
        for p in ("RZP", "REF", "ORDER", "ORD", "PAYMENT", "PAY", "TXN"):
            if t.startswith(p) and len(t) > len(p):
                remainder = t[len(p):]
                # If remainder starts with digits or letters, strip prefix
                if remainder:
                    t = remainder
                    break
        cleaned_tokens.append(t)
        
    if cleaned_tokens:
        canonical = "".join(cleaned_tokens)
    else:
        canonical = re.sub(r"[^A-Z0-9]", "", s)
        
    return canonical


def normalize_date(val: str | date | datetime | None) -> date:
    """Parse a date string into a standard datetime.date object.
    
    Supports:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - MM/DD/YYYY
        - DD-MM-YYYY
        - datetime / date instances
    """
    if val is None:
        raise ValueError("Date value cannot be None")
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()

    s = str(val).strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Unparseable date string: {val!r}")


def normalize_amount(val: Any) -> Decimal:
    """Parse a monetary amount string/number into exact 2-decimal place Decimal.
    
    Handles:
        - '₹5,000.00'   -> Decimal('5000.00')
        - '-$1,234.56'  -> Decimal('-1234.56')
        - '4975'        -> Decimal('4975.00')
        - 25.5          -> Decimal('25.50')
    """
    if val is None:
        raise ValueError("Amount cannot be None")
    if isinstance(val, Decimal):
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(val, (int, float)):
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    s = str(val).strip()
    # Remove currency symbols (INR ₹, USD $, EUR €, GBP £) and thousands commas
    s_cleaned = re.sub(r"[₹\$€£,\s]", "", s)

    if not s_cleaned:
        raise ValueError(f"Empty amount string: {val!r}")

    try:
        dec = Decimal(s_cleaned)
        return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as e:
        raise ValueError(f"Invalid monetary format: {val!r}") from e


def normalize_currency(val: str | None) -> str:
    """Normalize currency symbols and strings to canonical 3-letter ISO code."""
    if not val:
        return "INR"
    s = str(val).strip().upper()
    mapping = {
        "₹": "INR",
        "RS": "INR",
        "RS.": "INR",
        "RUPEES": "INR",
        "$": "USD",
        "USD": "USD",
        "EUR": "EUR",
        "€": "EUR",
        "GBP": "GBP",
        "£": "GBP",
    }
    return mapping.get(s, s)


# -----------------------------------------------------------------------------
# Record-Level Normalization Functions
# -----------------------------------------------------------------------------

def normalize_payment_row(row: dict[str, Any]) -> NormalizedPayment:
    return NormalizedPayment(
        payment_id=str(row["payment_id"]).strip(),
        order_id=str(row["order_id"]).strip(),
        amount=normalize_amount(row["amount"]),
        payment_date=normalize_date(row["payment_date"]),
        payment_method=str(row.get("payment_method", "UNKNOWN")).strip().upper(),
        status=str(row.get("status", "SUCCESS")).strip().upper(),
        raw_reference=str(row.get("reference", "")),
        canonical_reference=normalize_reference(row.get("reference", "")),
    )


def normalize_settlement_row(row: dict[str, Any]) -> NormalizedSettlement:
    gross = normalize_amount(row.get("gross_amount", 0))
    fee = normalize_amount(row.get("fee", 0))
    refund = normalize_amount(row.get("refund", 0))
    net = normalize_amount(row.get("net_amount", gross - fee - refund))

    return NormalizedSettlement(
        settlement_id=str(row["settlement_id"]).strip(),
        payment_reference=str(row.get("payment_reference", "")),
        canonical_reference=normalize_reference(row.get("payment_reference", "")),
        gross_amount=gross,
        fee=fee,
        refund=refund,
        net_amount=net,
        settlement_date=normalize_date(row["settlement_date"]),
        status=str(row.get("status", "SETTLED")).strip().upper(),
    )


def normalize_order_row(row: dict[str, Any]) -> NormalizedOrder:
    return NormalizedOrder(
        order_id=str(row["order_id"]).strip(),
        customer_id=str(row.get("customer_id", "")).strip(),
        amount=normalize_amount(row["amount"]),
        currency=normalize_currency(row.get("currency", "INR")),
        order_date=normalize_date(row["order_date"]),
        status=str(row.get("status", "PAID")).strip().upper(),
    )
