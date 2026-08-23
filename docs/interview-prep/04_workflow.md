# 4. End-to-End Workflow — Following a Transaction

## Workflow 1: Clean Match (Tier 1 — Exact Match)

**Scenario**: Customer pays ₹1,000 for order `ORD_001`. Payment `PAY_001` captured. Bank settles `STL_001` for ₹1,000 on the same day with reference `PAY_001`.

```
Step 1: NORMALISATION
  Input:  payment.reference = "PAY_001", amount = "₹1,000.00", date = "2025-01-15"
          settlement.reference = "PAY_001", net = "1000.00", date = "2025-01-15"
  Output: NormalizedPayment(ref="001", amount=Decimal("1000.00"), date=2025-01-15, currency="INR")
          NormalizedSettlement(ref="001", net=Decimal("1000.00"), date=2025-01-15)
  Note:   "PAY_" prefix stripped. "₹" and "," removed. Amount parsed to exact Decimal.

Step 2: CANDIDATE GENERATION
  For PAY_001: Find settlements within 7-day window where date diff ∈ [0, 7]
  Result: [STL_001] — only candidate within window

Step 3: SCORING
  ref_score   = 1.0   (exact canonical match: "001" == "001")
  amt_score   = 1.0   (exact amount: 1000.00 == 1000.00)
  date_score  = 1.0   (same day: T+0)
  curr_score  = 1.0   (both INR)
  total_score = 0.40(1.0) + 0.30(1.0) + 0.20(1.0) + 0.10(1.0) = 1.00

Step 4: ROUTING
  Score 1.00 >= 0.90 → HIGH_CONFIDENCE → Auto-Resolve Path

Step 5: SAFETY VALIDATION
  ✓ PAY_001 exists and unclaimed
  ✓ STL_001 exists and unclaimed
  ✓ |1000.00 - (1000.00 + 0.00)| = 0.00 ≤ 0.02
  ✓ 2025-01-15 >= 2025-01-15 (temporal valid)
  ✓ Confidence 1.00 >= 0.85
  → PASS: Commit match to database

Step 6: DATABASE COMMIT
  INSERT INTO reconciliation_results (payment_id='PAY_001', settlement_id='STL_001',
    match_score=1.00, status='AUTO_RESOLVED')
```

---

## Workflow 2: Fee Deduction Case (Tier 3)

**Scenario**: Payment of ₹1,000 via credit card. Bank settles ₹980 after 2% MDR fee.

```
Step 1: NORMALISATION
  Payment: ref="ABC123", amount=1000.00
  Settlement: ref="ABC123", net=980.00, fee=20.00

Step 3: SCORING
  ref_score  = 1.0   (exact match)
  amt_score  = ?     (1000.00 ≠ 980.00, but 1000.00 - 980.00 = 20.00 fee)
    → Check: |1000.00 - (980.00 + 20.00)| = 0.00 ≤ 0.02 → amt_score = 0.95
    → Verify fee %: 20.00/1000.00 = 2.0%, card range is [1.5%, 2.5%] → VALID
  date_score = 0.90  (T+2 delay)
  curr_score = 1.0
  total_score = 0.40(1.0) + 0.30(0.95) + 0.20(0.90) + 0.10(1.0) = 0.965

Step 4: ROUTING
  Score 0.965 >= 0.90 → HIGH_CONFIDENCE → Auto-Resolve Path
  (Note: Fee deductions with valid fee % still score high enough for auto-resolve)

Step 5-6: Same as Workflow 1 — validates and commits
```

---

## Workflow 3: Ambiguous Case → Agent Investigation (Tier 5 — Conflicting Duplicates)

**Scenario**: Payment of ₹500. Two settlements of ₹500 on the same day.

```
Step 3: SCORING
  Candidate A: STL_201, ref similar, ₹500, same day → score = 0.75
  Candidate B: STL_202, ref similar, ₹500, same day → score = 0.73
  Neither scores >= 0.90 (can't auto-resolve; ambiguous)

Step 4: ROUTING
  Scores 0.75 and 0.73, both in [0.50, 0.90) → MEDIUM_CONFIDENCE
  → Route to LangGraph Agent Investigation

Step 5: LANGGRAPH AGENT (4-node state machine)

  NODE 1: load_context
    Loads payment details and both candidate settlements
    Pre-scores them with the weighted scorer

  NODE 2: retrieve_policies
    Query: "multiple candidates same amount duplicate"
    RAG retrieves POL_005: "Conflicting Duplicate Candidate Escalation Policy"
    Policy says: "When 2+ candidates have similar scores and amounts,
    do NOT auto-match. Escalate to MANUAL_REVIEW."

  NODE 3: investigate_and_reason
    LLM/Mock examines evidence:
    - Two candidates with near-identical scores
    - POL_005 explicitly forbids autonomous matching
    Decision: action="MANUAL_REVIEW", confidence=0.55
    Evidence: "Two settlements (STL_201, STL_202) with identical amounts
              and dates. POL_005 requires human verification."

  NODE 4: validate_decision
    Safety validator checks decision:
    - action is "MANUAL_REVIEW" (no match to validate)
    → PASS: Create exception record, queue for human review

Step 6: HUMAN REVIEW QUEUE
  Exception created:
    payment_id: PAY_301
    reason: "CONFLICTING_DUPLICATE"
    ai_evidence: "POL_005 applied. Two candidates, ambiguous."
    status: PENDING_REVIEW
  
  Human reviewer sees both candidates side-by-side in Streamlit Tab 4
  Reviews evidence, clicks "Approve STL_201"
  → System re-validates through Safety Validator → commits
```

---

## Workflow 4: Missing Settlement (Tier 7)

```
Step 2: CANDIDATE GENERATION
  For PAY_401: No settlements found within 7-day window
  Result: [] — empty candidate list

Step 3: SCORING
  No candidates to score → Score = 0.0

Step 4: ROUTING
  Score 0.0 < 0.50 → LOW_CONFIDENCE → Exception Queue

Step 5: EXCEPTION CREATED
  reason_code: "MISSING_SETTLEMENT"
  evidence: "No settlement candidates found within 7-day settlement window"
  action_required: Investigate with bank; check for dropped webhooks
```

---

## System Flow Summary

```
                     500 Payments
                          │
                    ┌─────┴─────┐
                    │ NORMALIZE  │
                    │  & SCORE   │
                    └─────┬─────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
         HIGH (400)   MEDIUM (60)  LOW (40)
         Score≥0.90   0.50-0.90   Score<0.50
              │           │           │
              │     ┌─────┴─────┐     │
              │     │ LANGGRAPH │     │
              │     │  AGENT    │     │
              │     └─────┬─────┘     │
              │           │           │
              ▼           ▼           ▼
         ┌────────────────────────────────┐
         │      SAFETY VALIDATOR          │
         │  (all matches must pass)       │
         └───────────┬────────────────────┘
                     │
              ┌──────┴──────┐
              │             │
           PASS           FAIL
              │             │
         ┌────┴────┐  ┌────┴────┐
         │ COMMIT  │  │ HUMAN   │
         │ TO DB   │  │ REVIEW  │
         └─────────┘  └─────────┘
```

---

## 🎤 Probable Interview Questions

### Q: "Trace a single transaction through your entire system."
**A:** Use Workflow 1 above. Walk through each step: normalisation strips the `PAY_` prefix and parses `₹1,000.00` to `Decimal("1000.00")`. Candidate generation finds settlements within 7 days. Scoring computes 4 sub-scores (reference 1.0, amount 1.0, date 1.0, currency 1.0 = total 1.0). High confidence routes to auto-resolve. Safety validator checks 6 invariants — all pass. Match commits to PostgreSQL with ACID guarantees.

### Q: "What happens when the system encounters something it can't handle?"
**A:** "The system never guesses. If scoring produces a medium-confidence result, it routes to the LangGraph agent which retrieves relevant policies and makes a structured decision. If the agent itself is uncertain (like with conflicting duplicates), it returns MANUAL_REVIEW. If no candidates exist at all, it creates a MISSING_SETTLEMENT exception. Every uncertain case lands in the Human Review Queue with full evidence — the human reviewer sees the payment details, all candidate settlements, the AI's reasoning, and which policy was applied. The system errs on the side of caution."

### Q: "How does the fee deduction scoring work?"
**A:** "When the payment amount doesn't exactly match the settlement net, the scorer checks if the difference falls within known fee ranges. For a card payment, we expect a 1.5%–2.5% MDR fee. So for a ₹1,000 payment settling at ₹980, the fee is ₹20 (2.0%), which falls in the valid range. The scorer then verifies that Payment = Net + Fee (₹1,000 = ₹980 + ₹20) to within ₹0.02. If the balance equation holds and the fee percentage is within the expected range for that payment method, it gets a high amount score (0.95). This is not hardcoded — it's a real-time calculation using Python Decimal arithmetic."

### Q: "What's the difference between an 'exception' and a 'manual review' case?"
**A:** "An exception is created when the system has no viable match — like a missing settlement or a score below 0.50. Manual review is when the agent found a plausible match but isn't confident enough to auto-resolve — like conflicting duplicates where policy explicitly forbids autonomous matching. Both end up in the Human Review Queue, but exceptions typically need external investigation (checking with the bank) while manual reviews have candidates ready for the human to approve or reject."
