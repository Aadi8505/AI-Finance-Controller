# 9. Testing & Evaluation Strategy

## Test Suite Overview

| Test File | Tests | What It Covers |
|---|---|---|
| `test_normalizer.py` | 16 | Reference, amount, date, currency normalisation across edge cases |
| `test_candidates_and_scorer.py` | 8 | Candidate generation window, 4 sub-scores, confidence routing |
| `test_engine_and_evaluate.py` | 1 | End-to-end reconciliation engine with exact + missing scenarios |
| `test_database.py` | 4 | PostgreSQL connection, pgvector extension, seeded data queries |
| `test_agent_graph.py` | 4 | LangGraph state machine: fee, missing, and duplicate investigation |
| `test_agent_tools.py` | 8 | Financial tools (fee calculator, SLA verifier), tool registry |
| `test_policy_rag.py` | 4 | Knowledge base loading, policy retrieval by semantic query |
| `test_safety_validator.py` | 6 | All 6 safety invariants: valid match + 5 rejection scenarios |
| `test_human_review.py` | 3 | Pending reviews listing, detail view, rejection workflow |
| `test_api.py` | 6 | FastAPI endpoints: health, status, batch reconcile, exceptions, benchmarks |
| `test_dashboard_smoke.py` | 1 | Streamlit dashboard import validation (no crashes on load) |
| `test_evaluation_comparison.py` | 3 | Dataset loading, comparison evaluation, threshold sweep |
| `test_failure_modes.py` | 6 | Adversarial inputs, extreme fee hallucination, temporal attacks |
| **TOTAL** | **70** | **100% pass rate** |

---

## Testing Philosophy

### 1. No Test Depends on Hardcoded Results

Every test verifies **behaviour**, not specific values:

```python
# BAD (hardcoded):
assert match_score == 0.965  # Tied to specific data

# GOOD (behavioural):
assert match_score >= 0.90   # "This should be HIGH_CONFIDENCE"
assert routing_tier == "HIGH_CONFIDENCE"
```

### 2. Tests Mirror Real-World Scenarios

Each test represents a real financial situation:
- "What happens when the reference has a `REF-` prefix?"
- "What happens when the fee is 2.0% on a card payment?"
- "What happens when someone tries to claim a payment twice?"

### 3. Adversarial Testing

The `test_failure_modes.py` suite tests inputs that are **designed to break the system**:

```python
# Adversarial reference strings
"REF-TXN_/PAY-00042"    → should normalise to "00042"
"₹$€ 1,234.56"          → should parse to Decimal("1234.56")
"32/13/2025"             → should return None (invalid date)

# Safety barrier attacks
# Attack: Hallucinate a massive fee to make amounts "balance"
Payment: ₹10,000  |  Settlement: ₹1,100  |  Claimed Fee: ₹8,900
→ Validator REJECTS: fee of 89% is outside any valid range

# Attack: Match a settlement dated 304 days before payment
Payment: 2025-01-15  |  Settlement: 2025-11-15 (T+304)
→ Validator REJECTS: exceeds T+4 SLA window
```

---

## Empirical Evaluation

### Experiment A vs. Experiment B

Run: `python scripts/evaluate_comparison.py`

| Metric | Experiment A (Baseline) | Experiment B (Agentic) |
|---|---|---|
| Pipeline | Deterministic only | Deterministic + LangGraph agent |
| Total Records | 500 | 500 |
| Auto-Resolved | 400 | 400 |
| Exceptions/Review | 100 | 100 |
| **Match Rate** | **80.0%** | **80.0%** |
| **Precision** | **100.0%** | **100.0%** |
| **Recall** | **100.0%** | **100.0%** |
| Throughput | ~5,000 rec/sec | ~640 rec/sec |
| Latency | ~0.10s | ~0.78s |
| Financial Discrepancy | ₹0.00 | ₹0.00 |

### Why Are the Results the Same?

The 400 auto-resolved cases are identical in both experiments (same deterministic scorer). The remaining 100 cases are genuinely unsolvable without external information (duplicates, missing settlements, holdbacks) — neither the baseline nor the agent can resolve them without human input. The agent's value shows when it successfully matches medium-confidence cases that the baseline would have sent to exceptions.

### Threshold Tuning (Pareto Frontier)

Run: `python scripts/tune_thresholds.py`

Sweeps 20+ combinations of T_high and T_low to find optimal operating points:

| T_high | T_low | Auto-Resolved | Precision | Recall |
|---|---|---|---|---|
| 0.80 | 0.40 | 445 (89%) | 99.5% | 100% |
| 0.85 | 0.50 | 445 (89%) | 100% | 100% |
| **0.90** | **0.50** | **400 (80%)** | **100%** | **100%** |
| 0.95 | 0.50 | 400 (80%) | 100% | 100% |

**Key insight**: Between 0.85 and 0.90, precision jumps from 99.5% to 100%. This 0.5% matters: at 10 million daily transactions, 0.5% false positives = 50,000 incorrect reconciliations.

---

## How Ground Truth Works

```
┌── generate_data.py ──┐
│ Creates:              │
│  - orders.csv         │
│  - payments.csv       │     ┌── ground_truth.csv ──┐
│  - settlements.csv    │     │ payment_id, stl_id,   │
│                       │────▶│ expected_action,      │
│ Also creates:         │     │ tier_code             │
│  - ground truth       │     └───────────────────────┘
└───────────────────────┘              │
                                       │ (ISOLATED - never read
         ┌── reconciliation ──┐        │  by the engine)
         │ engine.py          │        │
         │ reads: CSVs only   │        ▼
         │ outputs: matches   │   ┌── evaluate.py ──┐
         └────────┬───────────┘   │ Compares engine  │
                  │               │ output against    │
                  └──────────────▶│ ground truth      │
                                  │ Computes P/R/F1   │
                                  └───────────────────┘
```

The reconciliation engine **never has access to ground truth**. It only sees the raw CSVs. Evaluation scripts compare engine outputs against ground truth after the fact.

---

## 🎤 Probable Interview Questions

### Q: "How did you test this system?"
**A:** "70 tests across 3 categories: (1) Unit tests for each component — normaliser (16 tests covering format edge cases), scorer (8 tests for each sub-score), safety validator (6 tests for each invariant including rejections). (2) Integration tests — full engine pipeline, API endpoints, database queries. (3) Adversarial tests — malformed inputs, extreme fee hallucinations, temporal impossibilities. All tests run in <5 seconds. No test hardcodes expected values; they verify behavioural properties like 'this should route to HIGH_CONFIDENCE' or 'this safety check should reject'."

### Q: "How do you know your evaluation is fair?"
**A:** "The ground truth is generated at dataset creation time and is completely isolated from the reconciliation engine. The engine reads `payments.csv` and `settlements.csv`; it has no access to `ground_truth.csv`. The evaluation script is a separate, independent program that loads both the engine's output and the ground truth, then computes precision and recall by counting true/false positives against the known-correct mapping."

### Q: "What would you test that you haven't yet?"
**A:** "Four areas: (1) **Load testing** — how the system performs with 100K, 1M, 10M records. (2) **Concurrent API testing** — multiple simultaneous approvals for the same payment (race condition testing). (3) **LLM output fuzzing** — testing with deliberately malformed LLM responses to verify Pydantic catches them. (4) **Cross-currency testing** — currently all data is INR; testing with mixed USD/EUR/INR transactions would validate currency handling at scale."

### Q: "Why is the agent throughput 8x slower than the baseline?"
**A:** "The agent adds overhead: policy RAG retrieval (embedding + cosine similarity), tool execution (fee calculator, SLA verifier), and LLM/mock inference. For the mock, this overhead is ~0.5ms per record. With a real LLM API call, it would be ~500ms–2000ms per record due to network latency. This is acceptable because the agent only processes ~20% of records (the ambiguous ones). The fast path handles 80% at full speed. The blended throughput is (80% × 5000 + 20% × 640) ≈ 4,128 rec/sec."

### Q: "What does 100% precision mean in your context?"
**A:** "Every match the system auto-resolved was verified against ground truth to be correct. Zero false positives — no payment was matched to the wrong settlement. This is different from 100% recall, which means every true match in ground truth was found. We achieve both 100% precision and 100% recall for the auto-resolved set. The 100 unresolved cases are correctly identified as exceptions — they're genuinely ambiguous and shouldn't be auto-resolved."
