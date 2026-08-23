# 10. 📋 Priority Study Guide

> Study these topics in order. Higher priority = more likely to come up in the interview.

---

## 🔴 PRIORITY 1: Must Know (Will Definitely Be Asked)

### 1.1 — Project Elevator Pitch (2 minutes)
- What the project does, why it matters, key metrics
- **Study**: [01_project_overview.md](01_project_overview.md) → "Explain your project in 2 minutes" answer

### 1.2 — System Architecture & Data Flow
- 6-layer architecture, how data flows from CSV to committed match
- Two-speed hybrid design (deterministic fast path + agentic investigation)
- **Study**: [03_architecture.md](03_architecture.md) → Layer diagram + data flow
- **Study**: [04_workflow.md](04_workflow.md) → Workflow 1 (clean match trace)

### 1.3 — Why LangGraph? (vs. LangChain)
- State machine vs. chain, mandatory safety node, deterministic execution
- **Study**: [02_tech_stack.md](02_tech_stack.md) → "Why LangGraph Over LangChain" section
- **Study**: [07_agent_and_rag.md](07_agent_and_rag.md) → "Why a State Machine and Not a ReAct Loop"

### 1.4 — RAG Implementation
- How the policy knowledge base works
- How retrieval is done (embedding, cosine similarity, top-K)
- Why RAG over using LLM's pre-training knowledge
- **Study**: [07_agent_and_rag.md](07_agent_and_rag.md) → Part E: Policy RAG Retriever

### 1.5 — Safety & Why LLM Can't Do Math
- Why arithmetic is sandboxed in Python Decimal tools
- The 6 safety invariants
- Defence in depth concept
- **Study**: [08_safety_and_review.md](08_safety_and_review.md) → All parts
- **Study**: [07_agent_and_rag.md](07_agent_and_rag.md) → Part D: Sandboxed Financial Tools

### 1.6 — Key Tradeoffs
- Precision vs. auto-resolution rate (the most important one)
- Hybrid architecture vs. pure LLM
- Weighted formula vs. ML model (explainability)
- **Study**: [05_tradeoffs.md](05_tradeoffs.md) → Tradeoffs 1, 2, and 8

---

## 🟡 PRIORITY 2: Should Know (Likely To Be Asked)

### 2.1 — Scoring Formula Details
- 4 sub-scores: reference (40%), amount (30%), date (20%), currency (10%)
- Why those weights
- How fee-adjusted amount scoring works
- **Study**: [06_data_pipeline.md](06_data_pipeline.md) → Part D: Multi-Factor Weighted Scoring

### 2.2 — Database Design
- Why PostgreSQL + pgvector
- 10 tables and their relationships
- UNIQUE constraints for single-claim enforcement
- ACID guarantees for financial data
- **Study**: [03_architecture.md](03_architecture.md) → Database Schema section
- **Study**: [02_tech_stack.md](02_tech_stack.md) → "Why PostgreSQL" section

### 2.3 — Human-in-the-Loop Design
- What the reviewer sees, approval/rejection flow
- Why human approvals also pass through safety validator
- Audit trail design
- **Study**: [08_safety_and_review.md](08_safety_and_review.md) → Parts E and F

### 2.4 — Testing Strategy
- 70 tests, behavioural assertions (not hardcoded)
- Adversarial testing approach
- Ground truth isolation
- **Study**: [09_testing_and_evaluation.md](09_testing_and_evaluation.md) → All sections

### 2.5 — Evaluation Methodology
- Experiment A vs. B comparison
- Why results are the same (and why that's expected)
- Pareto frontier threshold tuning
- **Study**: [09_testing_and_evaluation.md](09_testing_and_evaluation.md) → Empirical Evaluation section

---

## 🟢 PRIORITY 3: Good To Know (Might Be Asked)

### 3.1 — Data Normalisation Details
- 4 normalisation functions and edge case handling
- Why reference canonicalisation matters
- **Study**: [06_data_pipeline.md](06_data_pipeline.md) → Part B: Deterministic Normalisation

### 3.2 — Mock LLM Design
- How the deterministic mock works
- Why it's not "cheating"
- How it transparently upgrades to real GPT
- **Study**: [07_agent_and_rag.md](07_agent_and_rag.md) → Part F: The Mock Reasoner
- **Study**: [05_tradeoffs.md](05_tradeoffs.md) → Tradeoff 3

### 3.3 — API Design
- FastAPI endpoints and their purposes
- Pydantic request/response validation
- **Study**: [03_architecture.md](03_architecture.md) → Layer 6 table

### 3.4 — Streamlit Dashboard
- 5 tabs and their purposes
- Why Streamlit over React
- **Study**: [05_tradeoffs.md](05_tradeoffs.md) → Tradeoff 6

### 3.5 — Production Scaling
- What would change for 10M transactions
- Kafka, Celery, PgBouncer, React
- **Study**: [02_tech_stack.md](02_tech_stack.md) → "What would you change for production"
- **Study**: [05_tradeoffs.md](05_tradeoffs.md) → "If you had more time" answer

---

## 🔵 PRIORITY 4: Bonus Knowledge (Impressive If You Know)

### 4.1 — Financial Domain Knowledge
- What is MDR (Merchant Discount Rate)?
  - Fee charged by payment gateways (1.5%–2.5% for cards, 0%–1.1% for UPI)
- What is T+2 settlement?
  - Bank settles 2 business days after payment capture
- What is a rolling reserve?
  - Gateway withholds 10%–20% of settlement as fraud/chargeback protection
- What is reconciliation in accounting?
  - Verifying that two independent records of the same transaction agree

### 4.2 — LangGraph Internals
- `StateGraph` → `compile()` → runnable graph
- `TypedDict` for state schema
- Edge functions for conditional routing
- `END` sentinel for terminal nodes

### 4.3 — Vector Similarity Basics
- Cosine similarity = dot product of unit vectors
- L2 normalisation = divide by magnitude
- Why cosine > Euclidean for text embeddings (length-invariant)

### 4.4 — Python Decimal Module
- `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` (True)
- `0.1 + 0.2 == 0.3` (False in floating point)
- Why financial systems must use Decimal

---

## 📝 Quick-Fire Question Prep

Practice answering these in 30 seconds each:

| # | Question |
|---|---|
| 1 | What does your project do? |
| 2 | What problem does it solve? |
| 3 | What's a payment-settlement reconciliation? |
| 4 | Why can't you just match on transaction ID? |
| 5 | What is LangGraph and why did you use it? |
| 6 | What is RAG and how does it work here? |
| 7 | Why can't the LLM do the math? |
| 8 | What are the safety invariants? |
| 9 | What's the biggest tradeoff you made? |
| 10 | How did you test it? |
| 11 | What's your precision and recall? |
| 12 | Why is auto-resolve only 80%? |
| 13 | What would you change for production? |
| 14 | Why PostgreSQL and not MongoDB? |
| 15 | What's a Pareto frontier in your context? |
| 16 | How do you prevent double-claiming? |
| 17 | What happens when the system doesn't know? |
| 18 | Is anything hardcoded? |
| 19 | How does the human review queue work? |
| 20 | What would you do differently if you started over? |

---

## 🎯 Study Schedule Suggestion

| Time Available | What to Cover |
|---|---|
| **30 minutes** | Priority 1 only (sections 1.1–1.6). Read the Q&A answers aloud. |
| **1 hour** | Priority 1 + Priority 2. Understand scoring formula and DB design. |
| **2 hours** | Priority 1 + 2 + 3. Read all documents. Practice the quick-fire questions. |
| **3+ hours** | All priorities. Read source code for `scorer.py`, `validator.py`, and `reconciliation_graph.py`. Run the demo walkthrough yourself. |
