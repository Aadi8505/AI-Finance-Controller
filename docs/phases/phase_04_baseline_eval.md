# Phase 4: Deterministic Baseline Engine & Evaluation Suite (Experiment A)

- **Priority**: 🔴 CORE
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
1. Build the deterministic reconciliation engine loop (`engine.py`) integrating Candidate Generation, Scorer, and Claim Allocation without LLMs.
2. Establish a structured Exception taxonomy (`exceptions.py`) for all unresolved items.
3. Build the objective Evaluation Harness (`scripts/evaluate.py`) to measure Experiment A against the held-out ground truth dataset.

---

## 2. Implemented Code & Files

### Reconciliation Engine
- **File**: [`backend/app/reconciliation/engine.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/reconciliation/engine.py)
- **Key Mechanics**:
  - Implements single-claim allocation (`claimed_settlements` set) to prevent duplicate assignment.
  - Multi-candidate conflict detection: flags ambiguous ties when two candidates have near-identical high scores.
  - Returns strongly-typed `ReconciliationRunResult` tracking throughput, matches, and exceptions.

### Standardized Exception Taxonomy
- **File**: [`backend/app/reconciliation/exceptions.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/backend/app/reconciliation/exceptions.py)
- **Reason Codes**:
  - `UNMATCHED_AMOUNT`, `MISSING_SETTLEMENT`, `AMBIGUOUS_DUPLICATE`, `POLICY_VIOLATION`, `PARTIAL_SETTLEMENT`, `LOW_CONFIDENCE`.

### Evaluation Harness
- **File**: [`scripts/evaluate.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/scripts/evaluate.py)
- **Mathematical Formulations**:
  $$\text{Match Rate} = \frac{\text{Correct Auto-Resolved Matches}}{\text{Total Valid Resolvable Records}}$$
  $$\text{Auto-Resolution Precision} = \frac{\text{Correct Auto-Resolutions}}{\text{Total Auto-Resolutions}}$$
  $$\text{False-Resolution Rate} = \frac{\text{Incorrect Auto-Resolutions}}{\text{Total Auto-Resolutions}}$$
  $$\text{Throughput} = \frac{\text{Records Processed}}{\text{Elapsed Seconds}}$$
- **Outputs**: Generates persistent report [`data/generated/baseline_metrics.json`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/data/generated/baseline_metrics.json).

---

## 3. Empirical Evaluation Results (Experiment A: 500 Records)

```
======================================================================
  Experiment A — Deterministic Baseline
======================================================================
Evaluated Records : 500 (Threshold T_high=0.90)
Elapsed Time      : 0.10s (5,001.5 records/sec)
----------------------------------------------------------------------
[*] Match Rate               : 100.0% (400 true matches resolved)
[*] Overall Accuracy         : 100.0%
[*] Auto-Resolution Precision: 100.0% (Honest precision)
[*] False-Resolution Rate    : 0.0% (Kept at 0.0%)
[*] Exception Rate           : 20.0% (100 exceptions routed)
----------------------------------------------------------------------
  SCENARIO PERFORMANCE BREAKDOWN
----------------------------------------------------------------------
Scenario Tier    | Total  | Matched  | Correct  | Exceptions
----------------------------------------------------------------------
EXACT            | 200    | 200      | 200      | 0         
DELAY            | 50     | 50       | 50       | 0         
FEE              | 75     | 75       | 75       | 0         
FORMATTING       | 75     | 75       | 75       | 0         
PARTIAL          | 50     | 0        | 0        | 50        
ADVERSARIAL      | 25     | 0        | 0        | 25        
MISSING          | 25     | 0        | 0        | 25        
======================================================================
```

---

## 4. Key Takeaways for Experiment B
- The deterministic engine successfully resolves 100% of clear cases (Exact, Formatting, Standard Fee, Standard Lag) at over **5,000 records/second**.
- It safely abstains on 100% of uncertain cases (Partial, Adversarial duplicates, Missing settlements) with **0.0% False Resolutions**.
- In **Phase 6 & 7 (LangGraph Agent & Tools)**, the agent will specifically target the ambiguous cases (Partial & Adversarial) to investigate policies and evidence.
