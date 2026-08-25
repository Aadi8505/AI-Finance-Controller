# 🧪 Custom Test Datasets (20 Rows Each)

This folder contains **2 clean, standalone sets of test CSVs** (20 entries each) that you can drag-and-drop directly into **Tab 2** of the dashboard to test and analyze reconciliation results.

---

## 📂 Folder Structure

```
custom_test_data/
├── set_1_standard/
│   ├── payments.csv       (20 payments across UPI, Card, Netbanking, Wallet)
│   └── settlements.csv    (20 matching bank settlements with standard fees and T+1/T+2 lags)
│
└── set_2_edge_cases/
    ├── payments.csv       (20 payments with challenging real-world scenarios)
    └── settlements.csv    (18 settlements with duplicates, partial holdbacks & missing payouts)
```

---

## 1. Set 1: Standard Payouts (`set_1_standard`)
* **Total Transactions**: 20 Payments, 20 Settlements.
* **Scenarios Covered**:
  - Clean 1:1 same-day matches (`PAY_1001`, `PAY_1004`, `PAY_1008`).
  - Standard card fees of 1.8% (`PAY_1002`, `PAY_1005`, `PAY_1007`, `PAY_1010`).
  - Netbanking fees of 1.5% (`PAY_1003`, `PAY_1009`, `PAY_1016`).
  - Reference formatting noise (`PAY_1006` with slashes vs `SET_2006` without).
  - Banking settlement delays ($T+1$ to $T+2$ days).
* **Expected Result**: **20 / 20 (100%) Auto-Resolved Matches** with 0 Exceptions.

---

## 2. Set 2: Edge Cases & Stress Test (`set_2_edge_cases`)
* **Total Transactions**: 20 Payments, 18 Settlements.
* **Scenarios Covered**:
  - Clean & fee matches: 15 records auto-resolve cleanly.
  - Reference format variations: `RZP/REF/3003` and `REF-3004`.
  - **Conflicting Duplicates**: `PAY_3007` & `PAY_3008` (both ₹3,500 on 2026-03-04 with identical amounts) $\rightarrow$ escalated to **Human Review (POL_005)**.
  - **Partial Reserve Holdback**: `PAY_3012` (₹20,000 paid, bank settled ₹18,000 withholding 10% reserve) $\rightarrow$ escalated to **Human Review (POL_006)**.
  - **Missing Settlements**: `PAY_3019` (₹28,000) & `PAY_3020` (₹4,100) have no bank payout $\rightarrow$ flagged as **`MISSING_SETTLEMENT` Exceptions**.
* **Expected Result**: **15 Auto-Resolved Matches**, **5 Exceptions** for Human Review Queue.

---

## ❓ Do These Files Need `ground_truth.csv`?
**No!** 
The dashboard reconciles whatever files you upload completely dynamically using its multi-factor scoring formula and safety gates.
