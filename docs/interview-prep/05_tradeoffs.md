# 5. Design Tradeoffs & Decisions

Every engineering decision involves tradeoffs. This document explains what we chose, what we didn't, and **why**.

---

## Tradeoff 1: Precision vs. Auto-Resolution Rate

| Option | Precision | Auto-Resolve Rate |
|---|---|---|
| **Our choice: T_high = 0.90** | **100%** | **80%** |
| Aggressive: T_high = 0.80 | 99.5% | 89% |
| Conservative: T_high = 0.95 | 100% | 80% |

**Decision**: We chose T_high = 0.90 because in financial systems, a single false match is worse than 50 cases going to manual review. At 0.80, we get 9% more auto-resolution but introduce a 0.5% false positive rate — which at Razorpay's scale (millions of transactions) means thousands of incorrect reconciliations daily.

**How we verified**: We ran a grid sweep across 20+ threshold combinations using `scripts/tune_thresholds.py` and plotted the Pareto frontier. T_high = 0.90 sits at the optimal precision/recall/throughput sweet spot.

---

## Tradeoff 2: Hybrid Architecture (Deterministic + Agent) vs. Pure LLM

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: Hybrid** | Fast path at 5,000/sec; agent only when needed | Two codepaths to maintain |
| Pure LLM for everything | Simpler architecture | 640 rec/sec (8x slower); unpredictable costs; hallucination risk on every record |
| Pure deterministic only | Fastest; no LLM costs | Can't handle ambiguous cases; no policy reasoning |

**Decision**: Pure LLM is too slow and risky for clean records (80% of volume). Pure deterministic can't handle nuanced cases. The hybrid gives us the best of both: deterministic speed for clean records, agent intelligence for hard ones.

---

## Tradeoff 3: Mock LLM Fallback vs. Mandatory API Key

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: Deterministic mock with real LLM option** | Works offline; reproducible tests; demo-ready without API key | Mock doesn't capture full LLM reasoning capability |
| Require OpenAI API key | Real LLM reasoning | Can't demo without paid API key; non-deterministic tests |

**Decision**: For a hackathon/interview demo, the system must work without external API keys. The mock implements the same decision logic (fee checking, policy application, duplicate detection) deterministically. When `OPENAI_API_KEY` is set, it transparently upgrades to real GPT-4o-mini.

---

## Tradeoff 4: 7-Day Candidate Window vs. Wider/Narrower

| Window | Pros | Cons |
|---|---|---|
| 3 days | Fewer false candidates | Misses legitimate T+4 holiday delays |
| **Our choice: 7 days** | Catches all standard SLA delays (T+0 to T+4 + buffer) | More candidates to score per payment |
| 14 days | Maximum coverage | Too many spurious candidates; slower scoring |

**Decision**: Bank settlement SLAs are typically T+2 to T+4. We add a buffer for holidays and weekends, arriving at 7 days. Beyond 7, the probability of a legitimate match drops dramatically and the false candidate rate increases.

---

## Tradeoff 5: Custom RAG vs. LangChain VectorStore

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: Custom NumPy cosine similarity** | Zero external dependencies; sub-millisecond retrieval; full control | Must implement similarity ourselves |
| LangChain VectorStoreRetriever + FAISS | Pre-built abstraction | Heavy dependency; FAISS compilation issues on Windows; overkill for 7 docs |
| LangChain + Pinecone/Chroma | Scalable to millions of docs | Cloud dependency; unnecessary cost; network latency |

**Decision**: We have exactly 7 financial policies. A full vector database is extreme overengineering. Our custom retriever loads embeddings into a NumPy array, caches them to disk (`kb_embeddings.npy`), and computes cosine similarity in <1ms. If the knowledge base grew to thousands of documents, we'd switch to FAISS or pgvector's native similarity search.

---

## Tradeoff 6: Streamlit vs. React Dashboard

| Approach | Build Time | Maintainability | User Experience |
|---|---|---|---|
| **Our choice: Streamlit** | ~4 hours | Single Python file | Good for ops; limited customisation |
| React + TypeScript | ~2 weeks | Separate frontend repo | Polished; customer-facing ready |

**Decision**: This is an internal operations dashboard for finance teams, not a customer-facing product. Streamlit gets us 5 interactive tabs with live data in a single Python file. For production, we'd build a React dashboard with proper state management and authentication.

---

## Tradeoff 7: Single-Claim via DB Constraints vs. Application-Level Locks

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: DB UNIQUE constraints** | Atomic; race-condition-proof; survives application crashes | Can't soft-delete without schema change |
| Application-level mutex/locks | More flexible | Race conditions if app crashes mid-transaction; distributed lock complexity |
| Optimistic locking with version columns | Good concurrency | Retry complexity; potential livelocks |

**Decision**: Financial double-claiming is a critical failure mode. Database-level `UNIQUE(payment_id)` and `UNIQUE(settlement_id)` constraints are the only approach that's truly atomic. Even if the application crashes mid-transaction, the database will never allow a payment to be matched twice. This is the strongest guarantee available.

---

## Tradeoff 8: Weighted Score Formula vs. ML Model

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: Explicit weighted formula** | Transparent; auditable; explainable to regulators | May not capture complex non-linear patterns |
| Gradient boosted model (XGBoost) | Captures non-linear interactions | Black box; hard to explain to auditors; needs training data |
| Neural network | Maximum pattern recognition | Overkill; no interpretability; training pipeline complexity |

**Decision**: Financial regulators require explainability. When an auditor asks "why was this match made?", we can show: "reference similarity was 1.0 (40%), amount compatibility was 0.95 (30%), date proximity was 0.90 (20%), currency match was 1.0 (10%), total = 0.965". An XGBoost model would say "the model predicted 0.965" with no decomposable explanation. Weighted scores are also easier to tune and debug.

---

## Tradeoff 9: Synthetic Data vs. Real Data

| Approach | Pros | Cons |
|---|---|---|
| **Our choice: Realistic synthetic data** | No PII; covers all 7 edge cases; reproducible | May not capture all real-world anomalies |
| Real Razorpay data | Realistic distributions | PII concerns; NDA issues; can't share in repo |

**Decision**: Hackathon constraint — we can't use real financial data. Our generator creates realistic distributions across 7 difficulty tiers modelling every real-world scenario: fee deductions, timing delays, reference mismatches, duplicates, holdbacks, and missing settlements. The tier distribution (200 clean, 100 delayed, 60 fee, 40 ref, 40 dup, 30 hold, 30 missing) mirrors production ratios.

---

## 🎤 Probable Interview Questions

### Q: "What's the biggest tradeoff you made in this project?"
**A:** "Precision vs. auto-resolution rate. I could push auto-resolution from 80% to 89% by lowering the confidence threshold from 0.90 to 0.80, but that introduces a 0.5% false positive rate. In financial systems, false matches cascade — they create accounting discrepancies, trigger audits, and erode trust. I chose to maintain 100% precision and let the extra 9% go to human review, which is far cheaper than fixing incorrect reconciliations."

### Q: "Why not use a machine learning model for matching?"
**A:** "Two reasons. First, explainability — financial regulators need to understand why a match was made. My weighted formula decomposes into 4 interpretable sub-scores that any auditor can verify. A gradient-boosted model outputs a single opaque number. Second, data dependency — ML models need labelled training data. In a hackathon context, I'd need to generate synthetic training data, train a model, and then test it on different synthetic data, which is circular. The weighted formula with empirically tuned thresholds achieves 100% precision without needing training data."

### Q: "If you had more time, what would you change?"
**A:** "Three things: (1) Replace CSV batch processing with Kafka streaming for real-time reconciliation. (2) Build a React dashboard with RBAC for production use. (3) Add a feedback loop where human reviewer decisions retrain confidence thresholds automatically — a form of online learning that improves the auto-resolution rate over time while maintaining precision."

### Q: "Why did you use a mock LLM instead of always calling GPT?"
**A:** "Three reasons: (1) Reproducibility — tests must be deterministic; real LLM calls return different text each time. (2) Demo-readiness — the system should work without an API key. (3) Cost — at scale, calling GPT for every transaction is expensive; the mock proves the architecture works and transparently upgrades to real GPT when a key is configured. The mock implements the same decision tree the LLM would follow, validated against the same safety barriers."
