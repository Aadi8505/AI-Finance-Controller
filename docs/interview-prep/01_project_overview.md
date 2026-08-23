# 1. Project Overview — What It Does

## The One-Line Pitch

> An AI-powered autonomous financial reconciliation engine that matches payments to bank settlements with **100% precision**, using a hybrid of deterministic scoring and an LLM investigation agent grounded in financial policies.

---

## The Problem

In any payment platform (like Razorpay), three data streams flow independently:

```
Customer places order → Payment captured by gateway → Bank settles funds to merchant
```

**The catch**: These three streams are never perfectly aligned.

| Real-World Problem | Example |
|---|---|
| **Settlement delays** | Customer pays on Monday, bank settles on Wednesday (T+2) |
| **Fee deductions** | Customer pays ₹1,000 but merchant receives ₹980 after 2% card processing fee |
| **Reference key mismatches** | Payment system says `TXN_12345`, bank says `REF-12345` |
| **Duplicate conflicts** | Two settlements of ₹500 on the same day — which one matches which payment? |
| **Partial holdbacks** | Gateway withholds 15% as rolling reserve; merchant gets only ₹850 of ₹1,000 |
| **Missing settlements** | Payment recorded but bank never settled (dropped webhook) |

**Manual reconciliation** at scale (millions of transactions/day) is:
- Slow (humans checking spreadsheets)
- Error-prone (wrong matches cause accounting discrepancies)
- Expensive (dedicated ops teams)

---

## What This System Does

It takes raw payment and settlement data and automatically:

1. **Cleans and normalises** messy references, amounts, dates, and currencies
2. **Scores every possible payment↔settlement pair** across 4 dimensions
3. **Auto-resolves clean matches** at >5,000 records/sec with zero false positives
4. **Investigates ambiguous cases** using an LLM agent that consults written accounting policies
5. **Blocks unsafe matches** with a mathematical safety gate (checks exact balance conservation)
6. **Queues truly uncertain cases** for human review with full AI evidence

---

## Who Is It For?

- **Fintech companies** (Razorpay, Stripe, PayU) doing daily bank reconciliation
- **E-commerce platforms** reconciling gateway payouts to order records
- **Finance/accounting teams** doing month-end close with large transaction volumes

---

## Key Metrics Achieved

| Metric | Value |
|---|---|
| Precision (zero false matches) | **100%** |
| Recall (no true match missed) | **100%** |
| Auto-resolution rate | **80%** (400/500 auto-resolved, remaining 100 are genuinely ambiguous) |
| Throughput (fast path) | **>5,000 records/sec** |
| Total financial discrepancy | **₹0.00** |
| Test coverage | **70 tests, 100% pass** |

---

## What Makes It Different From a Simple Rule-Based Matcher?

| Approach | Limitation | How We Solve It |
|---|---|---|
| Exact-match on reference ID | Fails when references have different formats | We canonicalise references (strip prefixes, normalize case) |
| Fixed threshold matching | Can't handle fee deductions | We calculate expected fee ranges per payment method |
| Pure LLM-based matching | LLMs hallucinate numbers | We sandbox all arithmetic into Python Decimal tools; LLM can't do math |
| Single-pass matching | Misses edge cases | Two-speed architecture: fast deterministic + deep agent investigation |

---

## 🎤 Probable Interview Questions

### Q: "Explain your project in 2 minutes."
**A:** "I built an autonomous financial reconciliation engine for matching payment gateway transactions to bank settlement records. The core challenge is that these records don't align perfectly — banks deduct fees, settle days later, and use different reference formats. My system uses a two-speed hybrid architecture: a high-throughput deterministic pipeline that auto-resolves 80% of records at 5,000/sec with 100% precision, and a LangGraph agent that investigates ambiguous cases by retrieving written accounting policies and executing sandboxed arithmetic tools. Before any match commits, a mathematical safety barrier verifies exact monetary conservation. The system achieved zero false matches across 500 test records spanning 7 difficulty tiers."

### Q: "Why is this problem hard? Can't you just match on transaction ID?"
**A:** "Transaction IDs across systems don't match perfectly — one says `TXN_12345`, another says `REF-12345`. Beyond that, amounts differ due to fee deductions (a ₹1,000 payment settles as ₹980 after 2% MDR), settlements arrive days later, and sometimes multiple transactions have the same amount on the same day. The real difficulty is doing this at scale with zero tolerance for false matches — an incorrect reconciliation creates an accounting discrepancy that cascades through financial statements."

### Q: "What's the business impact?"
**A:** "For a company like Razorpay processing millions of daily transactions, even a 1% manual reconciliation rate means thousands of transactions need human review daily. This system automates 80% with perfect precision, and for the remaining 20%, it provides structured AI investigation evidence so human reviewers can decide in seconds instead of minutes. At scale, this saves hundreds of ops-hours per month and eliminates accounting errors."

### Q: "Why 80% auto-resolution and not higher?"
**A:** "The remaining 20% are genuinely ambiguous cases by design — conflicting duplicates, partial holdbacks, and missing settlements. These are cases where even a perfect algorithm should escalate rather than guess. Pushing auto-resolution higher would sacrifice precision, and in financial systems, a single false match can trigger audit failures. The 0.90 confidence threshold was empirically tuned via a Pareto frontier sweep to maximize throughput while maintaining 100% precision."

### Q: "Is this production-ready?"
**A:** "It's a production-grade prototype. The core engine, safety barriers, and database layer are production-quality with ACID guarantees and unique constraints. For actual production, I'd add: (1) horizontal scaling with async task queues (Celery/SQS), (2) real-time streaming ingestion instead of batch CSV, (3) authentication/RBAC on the API, and (4) monitoring dashboards (Prometheus/Grafana). The architecture was designed with these extensions in mind."
