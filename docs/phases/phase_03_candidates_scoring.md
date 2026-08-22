# Phase 3: Candidate Generation & Weighted Scoring

- **Priority**: 🔴 CORE
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
1. Implement deterministic filtering to restrict large settlement ledger sets to small candidate subsets per payment.
2. Implement an empirical multi-factor scoring model to compute match confidence without calling LLMs.
3. Establish confidence-based routing tiers (`HIGH_CONFIDENCE`, `MEDIUM_CONFIDENCE`, `LOW_CONFIDENCE`).

---

## 2. Implemented Code & Files

### Candidate Generation
- **File**: [`backend/app/reconciliation/candidates.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/reconciliation/candidates.py)
- **Function**: `generate_candidates(payment, settlements, window_days=7, amount_tolerance_pct=0.25, max_candidates=10)`
- **Filters**:
  - Temporal lag: $0 \le (\text{settlement\_date} - \text{payment\_date}) \le 7\text{ days}$.
  - Monetary range: Gross/Net within $\pm 25\%$ (allowing for standard processing fee deductions and partial settlements).
  - Excludes cancelled/failed records.

### Multi-Factor Scoring & Confidence Routing
- **File**: [`backend/app/reconciliation/scorer.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/reconciliation/scorer.py)
- **Mathematical Formula**:
  $$\text{Score} = (0.40 \times S_{\text{ref}}) + (0.30 \times S_{\text{amt}}) + (0.20 \times S_{\text{date}}) + (0.10 \times S_{\text{curr}})$$
  - $S_{\text{ref}}$: Reference key token/sequence similarity ($1.0$ exact, $0.9$ substring, diff ratio).
  - $S_{\text{amt}}$: Amount compatibility ($1.0$ exact penny match, $0.95$ standard $0.5\%-3.0\%$ fee deduction, $0.6$ partial reserve, $0.0$ mismatch).
  - $S_{\text{date}}$: Temporal lag score ($1.0$ for $T+0/T+1$, $0.85$ for $T+2/T+3$, $0.60$ for $T+4/T+5$, $0.0$ if preceding).
  - $S_{\text{curr}}$: Currency matching ($1.0$ matching, $0.0$ incompatible).

- **Routing Logic**:
  - $\text{Score} \ge T_{\text{high}} (0.90) \implies$ `HIGH_CONFIDENCE` (Auto-resolve candidate)
  - $T_{\text{low}} (0.50) \le \text{Score} < T_{\text{high}} \implies$ `MEDIUM_CONFIDENCE` (Route to Agent Investigation)
  - $\text{Score} < T_{\text{low}} \implies$ `LOW_CONFIDENCE` (Route directly to Exception Queue)

---

## 3. Unit Test Suite

- **File**: [`backend/tests/test_candidates_and_scorer.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/tests/test_candidates_and_scorer.py)
- **Coverage**:
  - `TestCandidateGeneration`: Date window bounds, amount bounds, exclusions.
  - `TestScorerComponents`: Exact reference matching, substring similarity, fee tolerance checks, date lag penalties.
  - `TestConfidenceRouting`: Exact match auto-approval, fee-deducted routing, and multi-candidate rank sorting.

---

## 4. Verification Results
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1
collected 24 items

backend/tests/test_candidates_and_scorer.py::TestCandidateGeneration::test_window_and_amount_filter PASSED
backend/tests/test_candidates_and_scorer.py::TestScorerComponents::test_reference_similarity PASSED
backend/tests/test_candidates_and_scorer.py::TestScorerComponents::test_amount_score_exact PASSED
backend/tests/test_candidates_and_scorer.py::TestScorerComponents::test_amount_score_with_fee PASSED
backend/tests/test_candidates_and_scorer.py::TestScorerComponents::test_date_score PASSED
backend/tests/test_candidates_and_scorer.py::TestConfidenceRouting::test_high_confidence_exact_match PASSED
backend/tests/test_candidates_and_scorer.py::TestConfidenceRouting::test_medium_confidence_fee_and_delay PASSED
backend/tests/test_candidates_and_scorer.py::TestConfidenceRouting::test_ranking_multiple_candidates PASSED
backend/tests/test_normalizer.py (16 tests) PASSED

============================= 24 passed in 0.08s ==============================
```
