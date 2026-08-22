# Phase 7: Sandboxed Agent Tools & Financial Arithmetic Isolation

- **Priority**: 🟡 RECOMMENDED
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
Provide the LangGraph investigation agent with controlled, deterministic Python tools for exact arithmetic calculations, SLA verification, and database record queries, ensuring the LLM is strictly isolated from calculating any numeric financial quantities directly.

---

## 2. Implemented Code & Files

### Financial Calculation Tools (Decimal Isolated)
- **File**: [`backend/app/agents/tools/financial_tools.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/agents/tools/financial_tools.py)
- **Functions**:
  - `calculate_fee_difference(payment_amount, settlement_net, payment_method)`:
    - Calculates $\text{fee} = \text{payment} - \text{settlement\_net}$ and fee percentage.
    - Evaluates against standard merchant fee schedule:
      - `UPI`: $0.0\% - 1.2\%$
      - `CARD`: $1.5\% - 2.5\%$
      - `NETBANKING`: $1.0\% - 2.0\%$
      - `WALLET`: $1.2\% - 2.2\%$
    - Returns structured validation and policy notes.
  - `verify_settlement_window(payment_date, settlement_date, max_lag_days=4)`:
    - Computes calendar day lag $\Delta_{\text{days}}$.
    - Checks against standard $T+2$ business day SLA policy.

### Database Query Tools
- **File**: [`backend/app/agents/tools/database_tools.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/agents/tools/database_tools.py)
- **Functions**:
  - `get_payment_details(payment_id)`: Fetches payment metadata, order details, and customer IDs.
  - `get_settlement_details(settlement_id)`: Fetches payout gross, fee, net, and date records.
  - `query_candidates_db(payment_id, window_days)`: Queries database and ranks candidates with score breakdowns.

### Tool Registry & Dispatcher
- **File**: [`backend/app/agents/tools/registry.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/agents/tools/registry.py)
- **Features**:
  - Exposes `OPENAI_TOOLS_SCHEMAS` for function calling.
  - `dispatch_tool_call(tool_name, tool_args)`: Executes tool and returns timed, structured `ToolTrace` (with latency in milliseconds) for audit logs.

---

## 3. Unit Test Suite

- **File**: [`backend/tests/test_agent_tools.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/tests/test_agent_tools.py)
- **Coverage**:
  - Card fee calculation and policy verification.
  - UPI zero-fee validation.
  - Excessive fee anomaly detection.
  - Settlement window $T+1$ and $T+10$ delay verification.
  - Tool schema definitions and dispatch latency tracking.

---

## 4. Verification Results
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1
collected 41 items

backend/tests/test_agent_tools.py (8 tests) PASSED
backend/tests/test_agent_graph.py (4 tests) PASSED
backend/tests/test_candidates_and_scorer.py (8 tests) PASSED
backend/tests/test_database.py (4 tests) PASSED
backend/tests/test_engine_and_evaluate.py (1 test) PASSED
backend/tests/test_normalizer.py (16 tests) PASSED

============================= 41 passed in 0.99s ==============================
```
