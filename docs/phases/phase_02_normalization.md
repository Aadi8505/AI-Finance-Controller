# Phase 2: Deterministic Normalization & Preprocessing

- **Priority**: 🔴 CORE
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
Build a 100% deterministic preprocessing and normalization layer at the system boundary to standardize messy real-world financial records without invoking non-deterministic LLMs.

---

## 2. Implemented Code & Files

### Core Normalization Module
- **File**: [`backend/app/reconciliation/normalizer.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/reconciliation/normalizer.py)
- **Functions Implemented**:
  - `normalize_reference(raw_ref: str | None) -> str`: Strips arbitrary delimiters (`-`, `/`, `_`, spaces), canonicalizes casing, and handles standalone and attached prefixes (`RZP`, `REF`, `ORD`, `ORDER`, `PAY`, `TXN`).
  - `normalize_date(val: Any) -> date`: Tolerant multi-format parsing for ISO (`YYYY-MM-DD`), Indian (`DD/MM/YYYY`, `DD-MM-YYYY`), and US (`MM/DD/YYYY`).
  - `normalize_amount(val: Any) -> Decimal`: Converts formatted currency strings (with commas, `₹`, `$`, `€`, `£`, and signs) into exact Python `Decimal` objects to prevent floating point inaccuracies.
  - `normalize_currency(val: str | None) -> str`: Standardizes currency symbols (`₹` $\to$ `INR`, `$` $\to$ `USD`, `€` $\to$ `EUR`) to 3-letter ISO codes.
  - `normalize_payment_row`, `normalize_settlement_row`, `normalize_order_row`: Transforms raw CSV dictionaries into strongly typed dataclasses.

---

## 3. Unit Test Suite

- **File**: [`backend/tests/test_normalizer.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/tests/test_normalizer.py)
- **Test Coverage**:
  - `TestReferenceNormalization`: 4 tests (clean refs, varied prefixes, edge cases, whitespace).
  - `TestDateNormalization`: 4 tests (ISO, Indian format, existing objects, invalid format exception).
  - `TestAmountNormalization`: 4 tests (plain numbers, symbols & commas, negative amounts, invalid string exception).
  - `TestCurrencyNormalization`: 2 tests (symbols to ISO, lowercase to ISO).
  - `TestRecordRowNormalization`: 3 tests (end-to-end row parsing for Payment, Settlement, and Order records).

---

## 4. Verification Results
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1
collecting ... collected 16 items

backend/tests/test_normalizer.py::TestReferenceNormalization::test_clean_reference PASSED
backend/tests/test_normalizer.py::TestReferenceNormalization::test_various_prefixes PASSED
backend/tests/test_normalizer.py::TestReferenceNormalization::test_edge_cases PASSED
backend/tests/test_normalizer.py::TestDateNormalization::test_iso_format PASSED
backend/tests/test_normalizer.py::TestDateNormalization::test_indian_format PASSED
backend/tests/test_normalizer.py::TestDateNormalization::test_existing_date PASSED
backend/tests/test_normalizer.py::TestDateNormalization::test_invalid_date PASSED
backend/tests/test_normalizer.py::TestAmountNormalization::test_plain_numbers PASSED
backend/tests/test_normalizer.py::TestAmountNormalization::test_currency_symbols_and_commas PASSED
backend/tests/test_normalizer.py::TestAmountNormalization::test_signed_amounts PASSED
backend/tests/test_normalizer.py::TestAmountNormalization::test_invalid_amount PASSED
backend/tests/test_normalizer.py::TestCurrencyNormalization::test_symbols PASSED
backend/tests/test_normalizer.py::TestCurrencyNormalization::test_iso_codes PASSED
backend/tests/test_normalizer.py::TestRecordRowNormalization::test_payment_row PASSED
backend/tests/test_normalizer.py::TestRecordRowNormalization::test_settlement_row PASSED
backend/tests/test_normalizer.py::TestRecordRowNormalization::test_order_row PASSED

============================= 16 passed in 0.05s ==============================
```
