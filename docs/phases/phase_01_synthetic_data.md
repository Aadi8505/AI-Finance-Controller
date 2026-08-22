# Phase 1: Synthetic Dataset & Ground Truth Generation

- **Priority**: 🔴 CORE
- **Status**: ✅ Completed & Verified
- **Date**: 2026-08-23

---

## 1. Objectives & Scope
Generate a synthetic financial dataset across the Razorpay lifecycle:
$$\text{Orders} \longrightarrow \text{Payments} \longrightarrow \text{Settlements}$$
Produce a completely isolated held-out ground-truth dataset for objective model evaluation (never exposed to inference agents).

---

## 2. Implemented Code & Files

### Generator Script
- **File**: [`scripts/generate_data.py`](file:///c:/Users/HP%20VICTUS/Desktop/AWS/RZP/ai-finance-controller/scripts/generate_data.py)
- **Key Characteristics**:
  - Deterministic execution with fixed seed (`SEED = 42`).
  - Supports dynamic record scaling (default: 500, scalable to 100 or 1,000+).
  - Exact financial calculations using Python `Decimal` (preventing floating point imprecision).

---

## 3. Data Schema & Models

### Orders Table (`data/generated/orders.csv`)
| Column | Type | Description | Example |
|---|---|---|---|
| `order_id` | `str` | Unique order identifier | `ORD_1001` |
| `customer_id` | `str` | Customer account identifier | `CUST_0005` |
| `amount` | `Decimal` | Gross order amount | `7304.00` |
| `currency` | `str` | ISO currency code | `INR` |
| `order_date` | `date` | Order timestamp | `2026-02-08` |
| `status` | `str` | Order state | `PAID` |

### Payments Table (`data/generated/payments.csv`)
| Column | Type | Description | Example |
|---|---|---|---|
| `payment_id` | `str` | Unique payment identifier | `PAY_5001` |
| `order_id` | `str` | Foreign key referencing Order | `ORD_1001` |
| `amount` | `Decimal` | Payment charge amount | `7304.00` |
| `payment_date` | `date` | Payment authorization date | `2026-02-08` |
| `payment_method` | `str` | Method: `UPI`, `CARD`, `NETBANKING`, `WALLET` | `WALLET` |
| `status` | `str` | Payment status | `SUCCESS` |
| `reference` | `str` | Raw reference code (with realistic formatting noise) | `RZP_REF_1001` |

### Settlements Table (`data/generated/settlements.csv`)
| Column | Type | Description | Example |
|---|---|---|---|
| `settlement_id` | `str` | Unique settlement payout identifier | `SET_9001` |
| `payment_reference` | `str` | Reference key on settlement ledger | `RZP_REF_1001` |
| `gross_amount` | `Decimal` | Gross payout amount | `7304.00` |
| `fee` | `Decimal` | Deducted payment processing fee | `0.00` |
| `refund` | `Decimal` | Deducted refund amount | `0.00` |
| `net_amount` | `Decimal` | Net payout: $\text{gross} - \text{fee} - \text{refund}$ | `7304.00` |
| `settlement_date` | `date` | Payout date ($T + \text{lag}$) | `2026-02-09` |
| `status` | `str` | Settlement state | `SETTLED` |

### Ground Truth Table (`data/ground_truth/ground_truth.csv`)
| Column | Type | Description | Example |
|---|---|---|---|
| `payment_id` | `str` | Evaluated payment identifier | `PAY_5001` |
| `expected_settlement_id` | `str \| None` | True matching settlement ID | `SET_9001` |
| `expected_status` | `str` | Expected outcome: `MATCH`, `AMBIGUOUS_REVIEW`, `UNMATCHED` | `MATCH` |
| `scenario_type` | `str` | Scenario category | `EXACT` |
| `expected_net` | `Decimal \| None` | Expected net settlement amount | `7304.00` |
| `notes` | `str` | Audit rationale | `Clean 1:1 match` |

---

## 4. Generated Scenario Distribution (500 Records)

```json
{
  "total_orders": 500,
  "total_payments": 500,
  "total_settlements": 500,
  "total_ground_truth_records": 500,
  "scenarios_breakdown": {
    "EXACT": 200,
    "FEE": 75,
    "FORMATTING": 75,
    "DELAY": 50,
    "PARTIAL": 50,
    "ADVERSARIAL": 25,
    "MISSING": 25
  },
  "expected_statuses": {
    "MATCH": 400,
    "AMBIGUOUS_REVIEW": 75,
    "UNMATCHED": 25
  },
  "seed": 42
}
```

---

## 5. Verification Results
- Executed: `python scripts/generate_data.py --records 500`
- Exit code: `0`
- All 4 CSVs generated with consistent UTF-8 formatting and correct headers.
- File integrity confirmed across all sample rows.
