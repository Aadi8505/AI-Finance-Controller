# 🧪 Custom Test Datasets (20 Rows Each: 14 Matches + 6 Exceptions)

Both datasets contain **20 records each** with an exact mix of **14 correct/auto-resolvable transactions** and **6 ambiguous/exception transactions** so you can personally test and verify the functionality of both the fast-path auto-resolver and the human review triage!

---

## 📂 Folder Structure

```
custom_test_data/
├── set_1_standard/
│   ├── payments.csv       (20 payments)
│   └── settlements.csv    (18 settlements)
│
└── set_2_edge_cases/
    ├── payments.csv       (20 payments)
    └── settlements.csv    (18 settlements)
```

---

## 🟢 Set 1: Standard Payouts (`custom_test_data/set_1_standard/`)

### Breakdown:
* **Auto-Resolving Matches (14 Records / 70%)**:
  1. `PAY_1001`: UPI clean match (₹5,000.00)
  2. `PAY_1002`: Card 1.8% MDR fee (₹12,500.00 $\rightarrow$ net ₹12,275.00)
  3. `PAY_1003`: Netbanking 1.5% fee (₹3,400.00 $\rightarrow$ net ₹3,349.00)
  4. `PAY_1004`: Wallet clean match with T+2 banking lag (₹8,900.00)
  5. `PAY_1005`: Card 1.8% MDR fee (₹15,000.00 $\rightarrow$ net ₹14,730.00)
  6. `PAY_1006`: Reference format mismatch (`RZP/REF/1006` vs `RZPREF1006`)
  7. `PAY_1007`: Card 1.8% MDR fee (₹24,500.00 $\rightarrow$ net ₹24,059.00)
  8. `PAY_1008`: UPI clean match (₹1,800.00)
  9. `PAY_1009`: Netbanking 1.5% fee (₹9,600.00 $\rightarrow$ net ₹9,456.00)
  10. `PAY_1010`: Card 1.8% MDR fee (₹43,000.00 $\rightarrow$ net ₹42,226.00)
  11. `PAY_1011`: UPI clean match (₹2,500.00)
  12. `PAY_1012`: Card 1.8% MDR fee (₹11,000.00 $\rightarrow$ net ₹10,802.00)
  13. `PAY_1013`: Wallet clean match (₹6,700.00)
  14. `PAY_1014`: Card 1.8% MDR fee (₹19,500.00 $\rightarrow$ net ₹19,149.00)

* **Exceptions & Flagged Cases (6 Records / 30%)**:
  15. `PAY_1015`: **Conflicting Duplicate** (₹3,100.00 matches two duplicate candidates `SET_2015A` and `SET_2015B`) $\rightarrow$ **`CONFLICTING_DUPLICATES` (POL_005)**
  16. `PAY_1016`: **Conflicting Duplicate** (₹3,100.00 duplicate candidate conflict) $\rightarrow$ **`CONFLICTING_DUPLICATES` (POL_005)**
  17. `PAY_1017`: **Partial Settlement** (₹14,200.00 paid, gateway settled ₹11,360.00 withholding 20% reserve) $\rightarrow$ **`PARTIAL_SETTLEMENT` (POL_006)**
  18. `PAY_1018`: **Excessive Fee Discrepancy** (₹5,800.00 UPI with 20% fee outside policy) $\rightarrow$ **`FEE_DISCREPANCY` (POL_002)**
  19. `PAY_1019`: **Missing Settlement** (₹22,000.00 with no bank settlement) $\rightarrow$ **`MISSING_SETTLEMENT`**
  20. `PAY_1020`: **Missing Settlement** (₹4,900.00 with no bank settlement) $\rightarrow$ **`MISSING_SETTLEMENT`**

---

## 🟡 Set 2: Edge Cases & Stress Test (`custom_test_data/set_2_edge_cases/`)

### Breakdown:
* **Auto-Resolving Matches (14 Records / 70%)**:
  1. `PAY_3001`: UPI clean match (₹1,000.00)
  2. `PAY_3002`: Card 1.8% fee (₹5,000.00 $\rightarrow$ net ₹4,910.00)
  3. `PAY_3003`: Format mismatch (`RZP/REF/3003` vs `RZPREF3003`)
  4. `PAY_3004`: Dirty reference prefix (`REF-3004` vs `3004`)
  5. `PAY_3005`: UPI clean match (₹1,500.00)
  6. `PAY_3006`: Card 1.8% fee (₹6,200.00 $\rightarrow$ net ₹6,088.40)
  7. `PAY_3007`: Card 1.8% fee (₹12,000.00 $\rightarrow$ net ₹11,784.00)
  8. `PAY_3008`: Netbanking 1.5% fee (₹4,500.00 $\rightarrow$ net ₹4,432.50)
  9. `PAY_3009`: Wallet clean match (₹9,000.00)
  10. `PAY_3010`: UPI clean match (₹1,800.00)
  11. `PAY_3011`: Card 1.8% fee (₹7,500.00 $\rightarrow$ net ₹7,365.00)
  12. `PAY_3012`: UPI small clean match (₹500.00)
  13. `PAY_3013`: Netbanking 1.5% fee (₹3,300.00 $\rightarrow$ net ₹3,250.50)
  14. `PAY_3014`: Card 1.8% fee (₹16,000.00 $\rightarrow$ net ₹15,712.00)

* **Exceptions & Flagged Cases (6 Records / 30%)**:
  15. `PAY_3015`: **Conflicting Duplicate** (₹4,200.00 with `SET_4015A` and `SET_4015B`) $\rightarrow$ **`CONFLICTING_DUPLICATES`**
  16. `PAY_3016`: **Conflicting Duplicate** (₹4,200.00 with `SET_4015A` and `SET_4015B`) $\rightarrow$ **`CONFLICTING_DUPLICATES`**
  17. `PAY_3017`: **Partial Settlement** (₹20,000.00 with 20% holdback, net ₹16,000.00) $\rightarrow$ **`PARTIAL_SETTLEMENT`**
  18. `PAY_3018`: **Excessive Fee Discrepancy** (₹2,200.00 with ₹440.00 fee) $\rightarrow$ **`FEE_DISCREPANCY`**
  19. `PAY_3019`: **Missing Settlement** (₹28,000.00 with no settlement) $\rightarrow$ **`MISSING_SETTLEMENT`**
  20. `PAY_3020`: **Missing Settlement** (₹4,100.00 with no settlement) $\rightarrow$ **`MISSING_SETTLEMENT`**

---

## 🎯 How to Run on Dashboard:
1. Open **Tab 2** on the Streamlit dashboard (`http://localhost:8501`).
2. Select **`📁 Mode 2: Upload Custom CSV Files`**.
3. Upload `payments.csv` and `settlements.csv` from either folder.
4. Click **`🚀 Ingest Custom CSVs & Run Reconciliation`**.
5. Observe:
   - **14 Auto-Resolved Matches** in Tab 2 Live Explorer.
   - **6 Exceptions** in Tab 4 Human Review Queue.
