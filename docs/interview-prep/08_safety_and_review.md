# 8. Safety, Validation & Human Review

## Part A: The Safety Validator — Why It Exists

### The Core Problem

In financial systems, there are things that must **never** happen:
- A payment matched to two different settlements (double-claim)
- A match where the money doesn't add up (₹1,000 payment matched to ₹500 settlement)
- A settlement dated before its payment (time travel)

The scorer can be tuned. The agent can be wrong. But the **safety validator is absolute** — it's the last line of defence before anything touches the database.

### File: `backend/app/reconciliation/validator.py`

---

## Part B: The 6 Safety Invariants

### Invariant 1: `PAYMENT_EXISTS`
```
Check: The payment ID exists in our records
Why:   Prevents matching to phantom/deleted payments
```

### Invariant 2: `SETTLEMENT_EXISTS`
```
Check: The settlement ID exists in our records
Why:   Prevents matching to non-existent settlements
```

### Invariant 3: `SINGLE_CLAIM` (Double-Allocation Prevention)
```
Check: Neither the payment nor settlement has been matched before
Why:   In accounting, every payment must reconcile to exactly one settlement
       and vice versa. Double-claiming creates phantom money.
       
Enforcement:
  - Application level: validator checks claimed_payments/claimed_settlements sets
  - Database level: UNIQUE(payment_id) and UNIQUE(settlement_id) constraints
  
This is dual-enforced because:
  - App-level catches it fast (in-memory set lookup)
  - DB-level catches race conditions (concurrent API requests)
```

### Invariant 4: `AMOUNT_CONSERVATION`
```
Check: |Payment Amount - (Settlement Net + Settlement Fee + Refund)| <= 0.02
Why:   Money cannot be created or destroyed. If ₹1,000 was paid, exactly ₹1,000
       must be accounted for across net payout, fees, and refunds.
       
The 0.02 tolerance handles:
  - Rounding in cross-currency conversions
  - Sub-paisa fractional differences
  - But NOT missing fees or incorrect matches
```

### Invariant 5: `TEMPORAL_VALIDITY`
```
Check: Settlement Date >= Payment Date
Why:   A bank cannot settle a payment before it was made.
       Violations indicate data corruption or timezone errors.
```

### Invariant 6: `CONFIDENCE_BAR`
```
Check: Match confidence score >= 0.85
Why:   Even if the amount and date look right, a low-confidence match
       suggests the scorer isn't sure. This catches edge cases where
       the wrong settlement happens to have similar amounts.
       
Note: This is LOWER than the auto-resolve threshold (0.90) because
      agent-investigated matches can have lower scorer confidence but
      high policy-grounded evidence.
```

---

## Part C: What Happens When Validation Fails

```
Match Proposal → Safety Validator
                      │
              ┌───────┴───────┐
           ALL PASS        ANY FAIL
              │               │
        Commit to DB    Divert to Human Review
        Status: AUTO_RESOLVED    Status: MANUAL_REVIEW
                              Reason: which invariant failed
                              Evidence: exact violation detail
```

**Key principle**: Failure is always **safe**. The system never rejects a transaction — it escalates to a human. No money is lost; resolution is just delayed.

---

## Part D: Defence in Depth

Multiple independent layers prevent errors:

```
Layer 1: SCORER
  - Assigns low scores to bad matches (filters 80%)
  
Layer 2: AGENT
  - Consults policies, rejects ambiguous cases
  
Layer 3: SAFETY VALIDATOR (this layer)
  - Mathematical verification of invariants
  
Layer 4: DATABASE CONSTRAINTS
  - UNIQUE indexes prevent double-claims even under concurrency
  
Layer 5: HUMAN REVIEW
  - Final human verification for escalated cases
```

If the scorer gets fooled → the agent catches it.
If the agent hallucinates → the validator catches it.
If the validator has a bug → the database constraint catches it.
If everything fails → a human reviews it.

---

## Part E: Human-in-the-Loop Review Queue

### File: `backend/app/services/human_review.py`

### What the Human Reviewer Sees (in Streamlit Tab 4)

For each pending review case:

```
┌─────────────────────────────────────────────────────┐
│ EXCEPTION #42: Payment PAY_301                      │
│ Reason: CONFLICTING_DUPLICATE                       │
│ Amount: ₹500.00                                     │
│ Payment Date: 2025-01-15                            │
│                                                     │
│ AI Evidence:                                        │
│ "Two settlements (STL_201, STL_202) have matching   │
│  amounts and dates. POL_005 applied — autonomous    │
│  matching forbidden."                               │
│                                                     │
│ Candidate Settlements:                              │
│ ┌───────────┬──────────┬────────────┬──────────┐   │
│ │ ID        │ Amount   │ Date       │ Score    │   │
│ ├───────────┼──────────┼────────────┼──────────┤   │
│ │ STL_201   │ ₹500.00  │ 2025-01-15 │ 0.75     │   │
│ │ STL_202   │ ₹500.00  │ 2025-01-15 │ 0.73     │   │
│ └───────────┴──────────┴────────────┴──────────┘   │
│                                                     │
│  [✅ Approve STL_201]  [✅ Approve STL_202]         │
│  [❌ Reject Both]                                   │
└─────────────────────────────────────────────────────┘
```

### What Happens When a Human Approves

```python
def approve_match(exception_id, settlement_id, reviewer_notes):
    # 1. Load the exception and payment details
    exception = get_exception(exception_id)
    
    # 2. RE-VALIDATE through Safety Validator
    #    (human decisions are NOT trusted blindly)
    validation = safety_validator.validate_match(
        payment=exception.payment,
        settlement=selected_settlement,
        confidence=0.90  # Human approval gets high confidence
    )
    
    if not validation.is_valid:
        raise ValidationError(validation.errors)
    
    # 3. Commit to database
    create_reconciliation_result(
        payment_id=exception.payment_id,
        settlement_id=settlement_id,
        status="HUMAN_APPROVED",
        reviewer=reviewer_notes
    )
    
    # 4. Mark exception as resolved
    update_exception(exception_id, status="RESOLVED")
    
    # 5. Write immutable audit entry
    create_audit_log(exception_id, "APPROVED", reviewer_notes)
```

**Critical detail**: Even human approvals pass through the Safety Validator. A human clicking "Approve" on a mathematically invalid match will be blocked. This prevents operator error from corrupting financial data.

### What Happens When a Human Rejects

```python
def reject_match(exception_id, reviewer_notes):
    # Mark as rejected with audit trail
    update_exception(exception_id, status="REJECTED")
    create_audit_log(exception_id, "REJECTED", reviewer_notes)
    # No match committed; payment remains unreconciled
```

---

## Part F: Audit Trail

Every action creates an immutable record:

| Event | What's Recorded |
|---|---|
| Auto-resolve | match_score, routing_tier, timestamp |
| Agent investigation | all tool calls with latency, policy citations, decision JSON |
| Safety validation failure | which invariant failed, exact values |
| Human approval | reviewer identity, selected settlement, audit notes |
| Human rejection | reviewer identity, rejection reason |

This enables:
- **Regulatory compliance**: Auditors can trace every reconciliation decision
- **Debugging**: If a match is wrong, we can see exactly why it was approved
- **Performance analysis**: Tool call latencies, agent reasoning quality

---

## 🎤 Probable Interview Questions

### Q: "Why do human decisions also go through the safety validator?"
**A:** "Defence in depth. Humans make mistakes — an operator might approve a match where the settlement is for ₹500 but the payment was ₹1,000, or approve a settlement that's already been claimed by another payment. By re-validating through the same mathematical invariants, we prevent operator error from corrupting financial data. The safety validator is the one component that trusts nobody — not the scorer, not the agent, not the human."

### Q: "What happens if the safety validator has a bug?"
**A:** "Database-level constraints act as the final safety net. Even if the validator's in-memory tracking has a bug and allows a double-claim, the database's `UNIQUE(payment_id)` constraint will reject the INSERT and raise an IntegrityError. This is why we use dual enforcement — application-level for speed, database-level for correctness under all circumstances including race conditions."

### Q: "How do you prevent race conditions in concurrent approvals?"
**A:** "Three mechanisms: (1) The application-level validator maintains in-memory sets of claimed payment/settlement IDs. (2) Database UNIQUE constraints prevent concurrent inserts of the same payment/settlement ID. (3) PostgreSQL's transaction isolation (SERIALIZABLE or READ COMMITTED) ensures atomic read-check-write sequences. In the current architecture, batch reconciliation runs are sequential. For production concurrent API requests, the DB constraint is the authoritative guardian."

### Q: "What does the audit trail look like?"
**A:** "Every reconciliation run creates a run record with timestamp and threshold parameters. Every match creates a result record with the score breakdown and routing tier. Every agent investigation creates records of all tool calls (with execution latency) and the full decision JSON. Every human review creates an audit entry with the reviewer's identity and notes. An auditor asking 'why was payment X matched to settlement Y?' can trace the full chain: which run, what score, which tools the agent called, what policies were retrieved, and who approved it."

### Q: "How does the 0.85 confidence bar differ from the 0.90 auto-resolve threshold?"
**A:** "The 0.90 threshold is for the scorer's fast path — only very high-confidence pairs auto-resolve without investigation. The 0.85 confidence bar in the safety validator is a lower floor that applies to all matches, including agent-investigated ones. An agent might investigate a case with a scorer confidence of 0.75 (MEDIUM tier) and, after consulting policies and running tools, determine it's a valid fee deduction with confidence 0.88. The safety validator accepts this because 0.88 >= 0.85. But a scorer confidence of 0.75 alone would never auto-resolve (0.75 < 0.90). The two thresholds serve different purposes at different layers."
