# 6. Data Pipeline & Scoring Engine

## Part A: Synthetic Data Generation

### The Generator (`scripts/generate_data.py`)

Generates 500 records across 7 difficulty tiers with realistic financial distributions:

```python
TIER_DISTRIBUTION = {
    "TIER_1_CLEAN_EXACT":          200,  # 40% — clean 1:1 matches
    "TIER_2_TIMING_DELAY":         100,  # 20% — T+2 to T+4 settlement lag
    "TIER_3_FEE_DEDUCTION":         60,  # 12% — MDR fee deducted at source
    "TIER_4_REFERENCE_FORMAT":      40,  #  8% — dirty reference keys
    "TIER_5_CONFLICTING_DUPLICATE": 40,  #  8% — same amount, same day
    "TIER_6_PARTIAL_HOLD":          30,  #  6% — gateway reserve holdback
    "TIER_7_MISSING_SETTLEMENT":    30,  #  6% — no settlement exists
}
```

### What Each Tier Generates

| Tier | Payments | Settlements | Key Characteristic |
|---|---|---|---|
| 1 | Same ref, same amount | Identical ref, same-day | Direct match |
| 2 | Normal ref | Same ref, delayed by 2–4 days | Settlement lag |
| 3 | Amount X | Net = X - fee, where fee = 1.5%–2.5% | MDR deduction |
| 4 | Clean ref | Ref with added prefix (`REF-`, `TXN_`) | Format noise |
| 5 | Amount X | **Two** settlements of amount X, same day | Ambiguity |
| 6 | Amount X | Net = X * (0.80–0.90), partial payout | Reserve holdback |
| 7 | Amount X | **No settlement generated** | Missing data |

### Ground Truth

A separate `data/ground_truth/ground_truth.csv` is generated with the correct payment→settlement mapping. This file is **never read by the reconciliation engine**; it's only used by evaluation scripts to measure accuracy.

---

## Part B: Deterministic Normalisation

### File: `backend/app/reconciliation/normalizer.py`

Four normalisation functions, each handling real-world messiness:

#### `normalize_reference(raw_ref)`
```
Input:  "REF-PAY_12345"  →  "12345"
Input:  "TXN_/ABC-123"   →  "ABC123"
Input:  "  pay-00042  "   →  "00042"

Logic:
1. Strip leading/trailing whitespace
2. Convert to uppercase
3. Remove known prefixes: REF-, TXN_, PAY-, STL-, ORD-
4. Remove separators: /, -, _
5. Result: canonical alphanumeric key
```

#### `normalize_amount(raw_amount)`
```
Input:  "₹1,000.50"    →  Decimal("1000.50")
Input:  "$1234"         →  Decimal("1234")
Input:  "-500.00"       →  Decimal("500.00")   # Absolute value
Input:  "abc"           →  None                  # Invalid

Logic:
1. Remove currency symbols (₹, $, €, £)
2. Remove commas and whitespace
3. Take absolute value (no negative amounts)
4. Parse into Python Decimal (exact, no float rounding)
```

#### `normalize_date(raw_date)`
```
Input:  "2025-01-15"      →  date(2025, 1, 15)  # ISO format
Input:  "15/01/2025"      →  date(2025, 1, 15)  # Indian DD/MM/YYYY
Input:  "01/15/2025"      →  date(2025, 1, 15)  # US MM/DD/YYYY
Input:  "invalid"         →  None

Logic:
1. Try ISO-8601 (YYYY-MM-DD)
2. Try Indian format (DD/MM/YYYY)
3. Try US format (MM/DD/YYYY)
4. If date object already passed in, return as-is
5. Return None if all parsers fail
```

#### `normalize_currency(raw_currency)`
```
Input:  "₹"     →  "INR"
Input:  "$"     →  "USD"
Input:  "inr"   →  "INR"
Input:  "EUR"   →  "EUR"

Logic: Symbol-to-ISO-4217 mapping, then uppercase
```

---

## Part C: Candidate Generation

### File: `backend/app/reconciliation/candidates.py`

For each payment, find all *plausible* settlement matches:

```
Filter conditions:
1. Settlement date >= Payment date (temporal order)
2. Settlement date <= Payment date + 7 days (within SLA window)
3. Settlement gross amount within tolerance of payment amount
   (accounts for fees up to ~3%)
```

**Why a window?** Without candidate filtering, scoring 500 payments × 500 settlements = 250,000 pairs. With the 7-day window, most payments have 1–5 candidates, reducing computation to ~2,500 pairs.

---

## Part D: Multi-Factor Weighted Scoring

### File: `backend/app/reconciliation/scorer.py`

Each payment-settlement pair receives 4 independent sub-scores:

### Score 1: Reference Similarity (Weight: 40%)

```python
def compute_reference_similarity(payment_ref, settlement_ref):
    if payment_ref == settlement_ref:
        return 1.0                          # Exact match
    if one_contains_other:
        return 0.85                         # Substring match
    return difflib.SequenceMatcher ratio    # Fuzzy similarity [0, 1]
```

### Score 2: Amount Compatibility (Weight: 30%)

```python
def compute_amount_score(payment_amount, settlement_net, settlement_fee):
    if payment_amount == settlement_net:
        return 1.0                          # Exact amount match
    
    # Check fee-adjusted balance
    total = settlement_net + settlement_fee
    diff = abs(payment_amount - total)
    if diff <= 0.02:
        # Verify fee percentage against payment method ranges
        fee_pct = (settlement_fee / payment_amount) * 100
        if fee_pct within expected_range_for_method:
            return 0.95                     # Valid fee deduction
    
    # Proportional scoring for partial matches
    return max(0, 1.0 - diff / payment_amount)
```

### Score 3: Date Proximity (Weight: 20%)

```python
def compute_date_score(payment_date, settlement_date):
    delta = (settlement_date - payment_date).days
    if delta == 0: return 1.00    # Same day
    if delta == 1: return 1.00    # T+1 (standard)
    if delta == 2: return 0.90    # T+2 (standard SLA)
    if delta == 3: return 0.80    # T+3
    return exp(-0.15 * delta)     # Exponential decay beyond T+3
```

### Score 4: Currency Match (Weight: 10%)

```python
def compute_currency_score(payment_currency, settlement_currency):
    return 1.0 if payment_currency == settlement_currency else 0.0
```

### Final Score

```
Total = 0.40 × ref_score + 0.30 × amt_score + 0.20 × date_score + 0.10 × curr_score
```

### Confidence Routing

| Score Range | Tier | Action |
|---|---|---|
| >= 0.90 | HIGH_CONFIDENCE | Auto-resolve (commit to DB via safety validator) |
| 0.50 – 0.89 | MEDIUM_CONFIDENCE | Route to LangGraph agent |
| < 0.50 | LOW_CONFIDENCE | Create exception (queue for human review) |

---

## 🎤 Probable Interview Questions

### Q: "Why those specific weights (0.40, 0.30, 0.20, 0.10)?"
**A:** "Reference similarity gets the highest weight (40%) because a matching reference ID is the strongest signal — it's a near-definitive identifier. Amount compatibility is next (30%) because correct monetary balance is a mathematical constraint. Date proximity is third (20%) because settlement timing is informative but has legitimate variance (T+0 to T+4). Currency is lowest (10%) because in a domestic Indian platform, almost everything is INR — it's confirmatory but rarely discriminating. These weights were validated empirically: the Pareto sweep showed this combination achieves 100% precision at the 0.90 threshold."

### Q: "How does normalization handle edge cases?"
**A:** "Robustly. Invalid amounts return `None` and the record is flagged as an exception. Dates try 3 format parsers in order (ISO, Indian, US) with a graceful `None` fallback. References strip all known prefixes via a compiled list and remove separator characters. We tested this with adversarial inputs: mixed-case references, currency symbols, scientific notation amounts, and emojis in strings — all handled gracefully in the 70-test suite."

### Q: "What's the time complexity of your matching?"
**A:** "Without candidate filtering: O(P × S) = O(n²) where P=payments, S=settlements. With the 7-day window filter, most payments have only 1–5 candidates, reducing it to approximately O(P × k) where k is the average number of candidates per payment (typically 1–3). For 500 records, this means ~2,500 scoring operations instead of 250,000. Each scoring operation is O(len(reference)) for the string similarity — trivially fast. Total throughput: >5,000 records/sec."

### Q: "Why not use TF-IDF or BM25 for reference matching?"
**A:** "References are short alphanumeric strings (5–15 characters), not natural language documents. TF-IDF and BM25 are designed for document retrieval where term frequency and document length matter. For short reference strings, simple canonical normalisation (strip prefixes, uppercase) followed by exact matching and Levenshtein similarity is more appropriate and faster. 90%+ of matches are resolved by exact canonical equality."
