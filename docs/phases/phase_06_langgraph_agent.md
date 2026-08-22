# Phase 6: LangGraph Investigation Agent

- **Priority**: 🟡 RECOMMENDED
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
Implement an autonomous, safe **LangGraph Investigation Agent** to investigate ambiguous financial records (medium-confidence cases) routed by the deterministic confidence router. Enforce structured Pydantic decision outputs and deterministic safety validation gates before any recommendation can be committed.

---

## 2. Implemented Code & Files

### Model & Provider Wrapper
- **File**: [`backend/app/core/model.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/core/model.py)
- **Features**:
  - Provider-isolated LLM layer with support for OpenAI (`gpt-4o-mini`) and deterministic offline mock fallback when `APP_USE_MOCK=1`.
  - Deterministic pseudo-embeddings (`_stable_vector()`) for offline test reproducibility.
  - Strict isolation: LLMs never perform financial arithmetic.

### Structured Decision Schema
- **File**: [`backend/app/agents/schemas/decision.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/agents/schemas/decision.py)
- **Schema**:
  ```python
  class AgentDecision(BaseModel):
      payment_id: str
      settlement_id: Optional[str] = None
      action: Literal["MATCH", "MANUAL_REVIEW", "EXCEPTION"]
      confidence: float = Field(ge=0.0, le=1.0)
      applied_policy_id: Optional[str] = None
      reason_codes: list[str] = []
      evidence_summary: str
  ```

### LangGraph State Machine
- **File**: [`backend/app/agents/graph/reconciliation_graph.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/agents/graph/reconciliation_graph.py)
- **Graph Nodes**:
  1. `load_context`: Prunes and scores plausible settlement candidates.
  2. `retrieve_policies`: Fetches relevant business policies (Settlement Lag $T+2$, UPI Fee, Card Fee, Conflict rules).
  3. `investigate_and_reason`: Invokes LLM / Mock reasoner with structured prompt to formulate hypothesis.
  4. `validate_decision`: Deterministic safety gate enforcing single-claim existence and exact monetary conservation: $|\text{Payment} - (\text{Net} + \text{Fee})| \le 0.05$.
- **Transitions**:
  $$\text{Entry} \to \text{load\_context} \to \text{retrieve\_policies} \to \text{investigate\_and\_reason} \to \text{validate\_decision} \to \text{END}$$

---

## 3. Unit Test Suite

- **File**: [`backend/tests/test_agent_graph.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/tests/test_agent_graph.py)
- **Coverage**:
  - `test_build_graph`: Verifies successful LangGraph compilation.
  - `test_agent_investigate_fee_case`: Validates fee-deducted payment investigation $\to$ `MATCH` $\to$ `AUTO_RESOLVED`.
  - `test_agent_investigate_missing_case`: Validates missing settlement investigation $\to$ `EXCEPTION`.
  - `test_agent_investigate_duplicate_conflict_case`: Validates conflicting duplicate candidates $\to$ `MANUAL_REVIEW`.

---

## 4. Verification Results
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1
collected 33 items

backend/tests/test_agent_graph.py (4 tests) PASSED
backend/tests/test_candidates_and_scorer.py (8 tests) PASSED
backend/tests/test_database.py (4 tests) PASSED
backend/tests/test_engine_and_evaluate.py (1 test) PASSED
backend/tests/test_normalizer.py (16 tests) PASSED

============================= 33 passed in 1.29s ==============================
```
