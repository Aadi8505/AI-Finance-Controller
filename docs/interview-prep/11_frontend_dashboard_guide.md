# 11. 🖥️ Frontend Dashboard & UI Glossary Guide

> Complete breakdown of every screen, metric card, slider, badge, data table, and financial term displayed on the **AI Finance Controller Dashboard** (`http://localhost:8501`).

---

## 📑 Table of Contents
1. [Sidebar & System Status Panel](#1-sidebar--system-status-panel)
2. [Tab 1: Executive KPI Overview](#2-tab-1-executive-kpi-overview)
3. [Tab 2: Batch Reconciliation Controller & Data Explorer](#3-tab-2-batch-reconciliation-controller--data-explorer)
4. [Tab 3: AI Investigation Workbench](#4-tab-3-ai-investigation-workbench)
5. [Tab 4: Human-in-the-Loop Review Queue](#5-tab-4-human-in-the-loop-review-queue)
6. [Tab 5: Empirical Evaluation & Benchmarks](#6-tab-5-empirical-evaluation--benchmarks)
7. [Comprehensive Financial & Technical Keywords Dictionary](#7-comprehensive-financial--technical-keywords-dictionary)
8. [🎤 Probable Interview Questions on the UI](#8--probable-interview-questions-on-the-ui)

---

## 1. Sidebar & System Status Panel

Located on the left of the dashboard. Provides persistent system health and knowledge grounding.

### Elements & What They Mean:
* **`Database: Connected`**: Confirms active connection to the database (PostgreSQL with `pgvector` or local SQLite fallback).
* **`PostgreSQL + pgvector: Active`**: Indicates vector similarity extension is loaded for embedding retrieval.
* **`LLM Provider: Mock (Deterministic) / OpenAI`**: Shows whether the system is using the deterministic offline reasoner (`APP_USE_MOCK=1`) or live GPT-4o-mini API.
* **`Safety Validator: Enforced`**: Confirms that every auto-match and human approval must pass the 6 pre-commit mathematical safety checks.
* **`Financial Policy Index (RAG)` (Expandable)**:
  - **`POL_001` (Settlement Lag SLA)**: Policy governing normal bank settlement lag ($T+0$ to $T+2$ days; up to $T+4$ for bank holidays).
  - **`POL_002` (UPI Fee Schedule)**: 0.0% fee for transactions $<₹2,000$, up to $1.1\%$ for larger merchant payments.
  - **`POL_003` (Card Processing Fees)**: Merchant Discount Rate (MDR) range between $1.5\%$ and $2.5\%$ for Credit/Debit cards.
  - **`POL_004` (Netbanking & Wallet Fees)**: Processing fee schedule between $1.0\%$ and $2.0\%$.
  - **`POL_005` (Duplicate Escalation Policy)**: Strict policy stating that if 2+ settlements have identical amounts and dates, auto-matching is **forbidden** and must escalate to human review.
  - **`POL_006` (Partial Holdbacks)**: Gateway rolling reserve policy where 10%–20% is held back for risk protection.
  - **`POL_007` (Refunds & Chargebacks)**: Accounting deductions for customer reversals.
* **`🧹 Clear All Reconciled Records` Button**: One-click demo reset that cleans all reconciliation results and exceptions back to initial 0 state.

---

## 2. Tab 1: Executive KPI Overview

The high-level command center for CFOs and Finance Operations managers.

### 5 Main Metric Cards:
1. **`Total Payments Ingested` (500)**: Total customer payment transactions loaded from the order management system.
2. **`Auto-Reconciled` (400 / 80.0%)**: Number and percentage of transactions successfully matched to bank settlements with high confidence ($\ge 0.90$).
3. **`Reconciled Volume` (₹7,118,500)**: Total monetary sum of all successfully reconciled payments.
4. **`Open Exceptions` (100 / 20.0%)**: Ambiguous or missing transactions currently flagged for investigation or human triage.
5. **`Resolved` (0 → N)**: Number of exceptions reviewed and resolved by human operators.

### Charts & Badges:
* **`Exceptions by Reason Code` (Bar Chart)**: Visual breakdown of why records were not auto-matched (`MISSING_SETTLEMENT`, `FEE_DISCREPANCY`, `CONFLICTING_DUPLICATES`, `TIMING_DELAY`, `PARTIAL_SETTLEMENT`).
* **`Exceptions by Review Status` (Bar Chart)**: Visual counts of `OPEN`, `RESOLVED`, and `REJECTED` exceptions.
* **`✓ 100% Precision Badge`**: Indicates zero false-positive matches (no payment matched to the wrong settlement).
* **`✓ 100% Recall Badge`**: Indicates all true matches in ground truth were identified.
* **`⚡ >5,000 rec/sec Throughput Badge`**: Processing speed of the deterministic fast-path engine.

---

## 3. Tab 2: Batch Reconciliation Controller & Data Explorer

Where operators run high-throughput batch reconciliation and inspect individual records.

### Interactive Controls:
* **`High Confidence Threshold (Auto-Resolve)` Slider ($T_{\text{high}}$)**: Default `0.90`. Pairs scoring above this threshold auto-resolve instantly.
* **`Low Confidence Threshold (Exception)` Slider ($T_{\text{low}}$)**: Default `0.50`. Pairs scoring below this threshold are marked as exceptions. Pairs between $T_{\text{low}}$ and $T_{\text{high}}$ ($[0.50, 0.90)$) route to the **LangGraph Investigation Agent**.
* **`Max Settlement Window (Days)`**: Default `7`. Candidate filtering parameter; only settlement records within 7 days of the payment date are evaluated.
* **`🚀 Run Batch Reconciliation` Button**: Triggers full normalization, scoring, safety checks, and database persistence.

### Live Metric Cards (Appears after run):
* **`Processed` (500)** | **`Auto-Resolved` (400 / 80%)** | **`Exceptions` (100 / 20%)** | **`Throughput` (>5,000 rec/sec)**.

### 🔍 Live Reconciled Data Explorer (Radio Toggle):
* **`🟢 Auto-Resolved Matches (Commit to Ledger)` Table**:
  - `Payment ID`: Unique payment transaction key (`PAY_5001`).
  - `Settlement ID`: Bank settlement payout ID (`SET_9001`).
  - `Amount Paid (₹)`: Gross amount charged to customer.
  - `Settlement Net (₹)`: Payout amount received in merchant bank account.
  - `Fee Deducted (₹)`: Gateway fee deducted (`Amount Paid - Settlement Net`).
  - `Discrepancy (₹)`: Unexplained monetary difference: $|\text{Paid} - (\text{Net} + \text{Fee})|$. Always `₹0.00`.
  - `Confidence Score`: Match score from weighted formula (e.g. `1.00`, `0.96`).
  - `Status`: `AUTO_RESOLVED`.
  - `Audit Note`: Mathematical explanation of the match.
* **`🟡 Flagged Exceptions (Awaiting Human Review)` Table**:
  - `Exception ID`: Unique tracking key (`EXC_ABCD12`).
  - `Payment ID`: Unmatched payment.
  - `Amount (₹)`: Payment amount.
  - `Reason Code`: Taxonomy classification (e.g. `CONFLICTING_DUPLICATES`, `MISSING_SETTLEMENT`).
  - `Severity`: Risk rating (`HIGH`, `MEDIUM`, `LOW`).
  - `Status`: Current state (`OPEN`).
  - `Candidate Settlements Count`: Number of potential bank payouts detected.
  - `Description`: Diagnostic reason for flagging.

---

## 4. Tab 3: AI Investigation Workbench

Interactive workbench for running the **LangGraph StateGraph Agent** on any specific payment.

### Elements & What They Mean:
* **`Payment Selector Dropdown`**: Allows picking any payment (e.g. `PAY_5007` with fee deduction, `PAY_5008` with format mismatch, `PAY_5011` with partial holdback).
* **`🔍 Run LangGraph Agent Investigation` Button**: Executes the 4-node agent state graph in real time.
* **`Status Badges`**:
  - `AUTO_RESOLVED` (Green) / `MANUAL_REVIEW` (Amber) / `EXCEPTION` (Red).
  - `Safety Gate: ✓ Passed` (Green) / `✗ Failed` (Red).
* **`Agent Decision Card`**:
  - **`Action`**: `MATCH`, `MANUAL_REVIEW`, or `EXCEPTION`.
  - **`Confidence`**: Agent's certainty score between `0.00` and `1.00`.
  - **`Applied Policy`**: Cites exact policy used (e.g. `POL_002` or `POL_003`).
  - **`Evidence Summary`**: Structured natural language rationale explaining the arithmetic and policy check.
* **`Audit Note Banner`**: Machine-verifiable audit trace of the investigation.
* **`Retrieved Policy RAG Passages Cards`**: Full text and summaries of the financial policies retrieved via cosine similarity.

---

## 5. Tab 4: Human-in-the-Loop Review Queue

The operational triage console where human accountants resolve ambiguous exceptions.

### Elements & What They Mean:
* **`Exception Selector Dropdown`**: Lists all 100 open exceptions with payment ID, amount, and reason code.
* **`Payment Details Panel (JSON)`**: Raw payment metadata (amount, currency, payment method, date, reference).
* **`Exception Diagnostics Card`**: Shows Reason Code, Severity badge (`HIGH`/`MEDIUM`), and diagnostic description.
* **`Candidate Settlements Table`**: Lists all plausible bank settlement candidates found within the 7-day window.
* **`Select Settlement to Match Dropdown`**: Allows the operator to pick which candidate is the legitimate match.
* **`Reviewer Audit Notes Textbox`**: Freeform notes entered by the operator for compliance auditing.
* **`✅ Approve Match` Button**: Triggers safety validation on the human selection. If the match passes the 6 safety invariants, it commits to `reconciliation_results` and marks the exception `RESOLVED`.
* **`❌ Reject Button`**: Marks the exception `REJECTED` and preserves the audit note without matching.

---

## 6. Tab 5: Empirical Evaluation & Benchmarks

The benchmark comparison tab comparing the two reconciliation approaches.

### Top Comparative Metric Cards:
* **`Match Rate`**: `80.0%` for Experiment B.
* **`Precision`**: `100.0%` (Zero false positives against isolated ground truth).
* **`Recall`**: `100.0%` (100% of true matches found).
* **`Throughput (Fast Path)`**: `>5,000 rec/sec`.

### Comparative Table:
| Metric | Experiment A (Baseline) | Experiment B (Agentic) | Explanation |
| :--- | :--- | :--- | :--- |
| **Pipeline Type** | Deterministic Baseline | Deterministic + LangGraph Agent | Architecture mode |
| **Total Records** | 500 | 500 | Dataset size |
| **Auto-Resolved** | 400 | 400 | Records matched without humans |
| **Exceptions** | 100 | 100 | Ambiguous cases escalated |
| **Match Rate** | 80.0% | 80.0% | Percentage auto-matched |
| **Precision** | 100.0% | 100.0% | Accuracy vs ground truth |
| **Latency** | ~0.10s | ~0.78s | Execution duration |
| **Throughput** | ~5,000 rec/sec | ~640 rec/sec | Records processed per second |

### Performance Breakdown by 7 Difficulty Tiers Table:
Displays total cases, auto-resolved counts, and true matches across:
1. `EXACT`: Clean 1:1 matches (200 records).
2. `DELAY`: Standard $T+2$ to $T+4$ banking lag (100 records).
3. `FEE`: MDR fee deducted at source (60 records).
4. `FORMATTING`: Dirty prefixes and separators (40 records).
5. `DUPLICATE`: Conflicting duplicate amounts on same day (40 records).
6. `PARTIAL`: Gateway reserve holdbacks (30 records).
7. `MISSING`: Dropped bank webhooks / missing payouts (30 records).

---

## 7. Comprehensive Financial & Technical Keywords Dictionary

| Keyword | Category | Definition |
| :--- | :---: | :--- |
| **Reconciliation** | Finance | Verifying that two independent financial records (payment gateway vs. bank settlement ledger) match and balance to ₹0.00. |
| **Settlement** | Finance | The actual transfer of funds from the acquiring bank / payment gateway to the merchant's bank account. |
| **MDR (Merchant Discount Rate)** | Finance | The fee percentage (1.5%–2.5% for cards, 0%–1.1% for UPI) deducted by the payment gateway before paying out funds. |
| **Settlement Lag (SLA)** | Finance | The standard time delay between payment capture and bank deposit ($T+0$ same day to $T+2$ business days). |
| **Rolling Reserve** | Finance | A percentage of funds (e.g. 10%–20%) withheld by the payment gateway to cover potential chargebacks or fraud. |
| **Chargeback / Refund** | Finance | Money returned to the customer due to a dispute or cancellation, deducted from settlement payouts. |
| **Discrepancy** | Accounting | Any unexplained monetary difference between the amount paid and the net settlement plus fees: $\|\text{Paid} - (\text{Net} + \text{Fee})\|$. |
| **Amount Conservation** | Accounting | Invariant stating money cannot be created or destroyed: $\text{Gross Payment} = \text{Net Settlement} + \text{Fee} + \text{Refund}$. |
| **Single-Claim Integrity** | Database | Ensuring a payment is matched to at most one settlement (and vice versa) to prevent double-counting. |
| **$T_{\text{high}}$ (0.90)** | Algorithm | Confidence threshold above which a candidate match is auto-resolved without human review. |
| **$T_{\text{low}}$ (0.50)** | Algorithm | Confidence threshold below which a transaction is immediately flagged as an exception. |
| **LangGraph** | AI / ML | A framework for building cyclic, state-machine agent workflows with explicit state transitions and mandatory validation nodes. |
| **Policy RAG** | AI / ML | Retrieval-Augmented Generation retrieving written financial policies (POL_001 to POL_007) based on vector cosine similarity. |
| **Sandboxed Arithmetic** | Software | Restricting all math calculations to pure Python `Decimal` tools so the LLM never performs arithmetic. |
| **Deterministic Fast Path** | Architecture | High-throughput rule-based pipeline that processes clean transactions at >5,000 rec/sec with 100% precision. |
| **Triage** | Operations | The human review process of inspecting flagged exceptions, evaluating candidates, and approving or rejecting matches. |
| **Audit Trail** | Compliance | An immutable, chronological record of every match, tool call, policy citation, and human approval for regulatory compliance. |

---

## 8. 🎤 Probable Interview Questions on the UI

### Q: "Walk me through what an operator sees when they open your dashboard."
**A:** "An operator sees a 5-tab executive console with a persistent sidebar. The sidebar displays live system health (database connection, pgvector status, and safety validator state) along with 7 grounded financial policies. In Tab 1, they see top-level KPIs: total payments ingested, matched percentage, reconciled volume in rupees, and open exceptions, along with bar charts classifying exceptions by reason code. In Tab 2, they can adjust confidence threshold sliders and trigger batch reconciliation, which updates a live Reconciled Data Explorer table. In Tab 3, they can pick any transaction and run the LangGraph agent to inspect its reasoning and retrieved policies. In Tab 4, they have the Human Review Queue to triage open exceptions with candidate tables and approve/reject buttons. Tab 5 shows live benchmark comparisons across all 7 difficulty tiers."

### Q: "What do the $T_{\text{high}}$ and $T_{\text{low}}$ sliders in Tab 2 actually control?"
**A:** "$T_{\text{high}}$ (default 0.90) is the auto-resolution threshold. Any payment-settlement pair with a multi-factor score $\ge 0.90$ is considered unambiguous and auto-resolves through the deterministic fast path. $T_{\text{low}}$ (default 0.50) is the exception floor. Any record with a score $< 0.50$ is flagged as an exception. The critical zone is between $0.50$ and $0.90$: these medium-confidence cases route to the LangGraph AI Investigation Agent to consult policies, verify fee schedules, and make a structured decision."

### Q: "In Tab 2's Data Explorer, what does 'Discrepancy' mean and why is it always ₹0.00?"
**A:** "Discrepancy is the unexplained difference: $|\text{Payment Amount} - (\text{Settlement Net} + \text{Fee Deducted})|$. In our auto-resolved matches, discrepancy is always ₹0.00 because our Pre-Commit Safety Validator enforces exact monetary balance conservation: $|\text{Payment} - (\text{Net} + \text{Fee})| \le 0.02$. If there were any unexplained difference, the safety validator would reject the match and divert it to Human Review. This guarantees zero financial drift."

### Q: "How does Tab 4 (Human Review Queue) protect against human operator mistakes?"
**A:** "When a human reviewer selects a candidate settlement and clicks 'Approve Match', the system does **not** blindly trust the human. The approval passes back through the deterministic `SafetyValidator.validate_match()`. If the human accidentally approves a settlement with the wrong amount, an already-claimed transaction, or an impossible date, the safety gate blocks the commit and displays an audit error. This provides defence-in-depth where neither the AI nor the human operator can violate fundamental accounting invariants."

### Q: "Why did you choose Streamlit for this UI instead of React?"
**A:** "This is an internal operations and audit console for finance teams, not a public consumer app. Streamlit allowed us to build 5 comprehensive, interactive tabs with live Pandas dataframes, real-time threshold sliders, and visual charts in pure Python with direct access to SQLAlchemy ORM models. It provides hot-reloading, zero frontend boilerplate, and native session management while delivering a custom CSS dark-theme aesthetic tailored for financial operations."
