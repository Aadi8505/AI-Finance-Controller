# 3. Architecture Deep Dive

## Layered Architecture

The system is organised into 6 layers, each with a single responsibility:

```
┌───────────────────────────────────────────────────────────┐
│                    LAYER 6: PRESENTATION                  │
│        Streamlit Dashboard  │  FastAPI REST API            │
├───────────────────────────────────────────────────────────┤
│                    LAYER 5: SERVICE                       │
│   Human Review Service  │  Reconciliation Engine          │
├───────────────────────────────────────────────────────────┤
│                    LAYER 4: AGENT                         │
│   LangGraph StateGraph  │  Policy RAG  │  Sandboxed Tools │
├───────────────────────────────────────────────────────────┤
│                    LAYER 3: SAFETY                        │
│              Deterministic Safety Validator                │
├───────────────────────────────────────────────────────────┤
│                    LAYER 2: SCORING                       │
│   Normalizer  │  Candidate Generator  │  Weighted Scorer  │
├───────────────────────────────────────────────────────────┤
│                    LAYER 1: DATA                          │
│       PostgreSQL + pgvector  │  CSV Files  │  JSONL KB    │
└───────────────────────────────────────────────────────────┘
```

---

## Component Map

### Layer 1: Data Layer
| Component | File | Purpose |
|---|---|---|
| Database Engine | `backend/app/db/database.py` | SQLAlchemy engine, session factory, connection pooling |
| Schema DDL | `backend/app/db/schema.sql` | 10 tables with constraints, foreign keys, pgvector columns |
| ORM Models | `backend/app/models/entities.py` | SQLAlchemy mapped classes for all 10 tables |
| Synthetic Data Generator | `scripts/generate_data.py` | Creates 500 orders/payments/settlements across 7 difficulty tiers |
| Database Seeder | `scripts/seed_database.py` | Loads CSV data into PostgreSQL |

### Layer 2: Scoring Layer
| Component | File | Purpose |
|---|---|---|
| Normalizer | `backend/app/reconciliation/normalizer.py` | Cleans references, amounts, dates, currencies into canonical form |
| Candidate Generator | `backend/app/reconciliation/candidates.py` | Filters plausible settlement matches within 7-day window |
| Weighted Scorer | `backend/app/reconciliation/scorer.py` | Computes 4-factor weighted score and routes by confidence tier |

### Layer 3: Safety Layer
| Component | File | Purpose |
|---|---|---|
| Safety Validator | `backend/app/reconciliation/validator.py` | Pre-commit gate enforcing 6 mathematical invariants |

### Layer 4: Agent Layer
| Component | File | Purpose |
|---|---|---|
| LangGraph Agent | `backend/app/agents/graph/reconciliation_graph.py` | 4-node state machine for investigating ambiguous cases |
| Decision Schema | `backend/app/agents/schemas/decision.py` | Pydantic model for structured agent output |
| Financial Tools | `backend/app/agents/tools/financial_tools.py` | Pure `Decimal` fee calculator and SLA verifier |
| Database Tools | `backend/app/agents/tools/database_tools.py` | Read-only DB query tools for the agent |
| Tool Registry | `backend/app/agents/tools/registry.py` | Registry of all tools with OpenAI function schemas |
| Policy RAG | `backend/app/rag/retriever.py` | Cosine similarity retriever over 7 financial policies |
| Knowledge Base | `data/policies/knowledge_base.jsonl` | 7 written financial policies (POL_001 to POL_007) |

### Layer 5: Service Layer
| Component | File | Purpose |
|---|---|---|
| Reconciliation Engine | `backend/app/reconciliation/engine.py` | Orchestrates the full fast-path pipeline |
| Exception Manager | `backend/app/reconciliation/exceptions.py` | Creates and manages exception records |
| Human Review Service | `backend/app/services/human_review.py` | CRUD operations for the review queue |

### Layer 6: Presentation Layer
| Component | File | Purpose |
|---|---|---|
| FastAPI App | `backend/app/main.py` | REST API entry point with CORS, routers |
| Reconciliation API | `backend/app/api/reconciliation.py` | `/api/reconcile/*` endpoints |
| Exceptions API | `backend/app/api/exceptions.py` | `/api/exceptions/*` endpoints |
| Investigation API | `backend/app/api/investigation.py` | `/api/investigate/*` endpoints |
| Benchmarks API | `backend/app/api/benchmarks.py` | `/api/benchmarks/*` endpoints |
| Streamlit Dashboard | `frontend/streamlit_app.py` | 5-tab operations console |

---

## Data Flow Diagram

```
Raw CSVs (orders.csv, payments.csv, settlements.csv)
        │
        ▼
┌─── NORMALIZER ──────────────────────────────┐
│  normalize_reference()  → canonical ref key  │
│  normalize_amount()     → Decimal            │
│  normalize_date()       → datetime.date      │
│  normalize_currency()   → ISO 4217 code      │
│  Output: NormalizedPayment, NormalizedSettl.  │
└──────────────┬──────────────────────────────┘
               ▼
┌─── CANDIDATE GENERATOR ─────────────────────┐
│  For each payment:                           │
│    Find settlements within 7-day window      │
│    Filter by gross amount ± tolerance        │
│  Output: List of candidate pairs             │
└──────────────┬──────────────────────────────┘
               ▼
┌─── WEIGHTED SCORER ─────────────────────────┐
│  Score = 0.40*ref + 0.30*amt + 0.20*date     │
│         + 0.10*currency                      │
│  Route by confidence tier:                   │
│    >= 0.90  → HIGH   → Auto-resolve path     │
│    >= 0.50  → MEDIUM → Agent investigation   │
│    <  0.50  → LOW    → Exception queue       │
└──────┬────────────┬────────────┬────────────┘
       │            │            │
   HIGH ▼        MEDIUM ▼      LOW ▼
       │            │            │
       │    ┌─── LANGGRAPH ──┐   │
       │    │ load_context   │   │
       │    │ retrieve_pols  │   │
       │    │ investigate    │   │
       │    │ validate       │   │
       │    └───────┬────────┘   │
       │            │            │
       ▼            ▼            ▼
┌─── SAFETY VALIDATOR ────────────────────────┐
│  ✓ Payment exists & unclaimed               │
│  ✓ Settlement exists & unclaimed            │
│  ✓ |Payment - (Net + Fee)| <= 0.02          │
│  ✓ Settlement date >= Payment date          │
│  ✓ Confidence >= 0.85                       │
│  Pass → commit to DB                        │
│  Fail → divert to Human Review              │
└─────────────────┬───────────────────────────┘
                  ▼
         ┌─── DATABASE ───┐
         │  PostgreSQL 16  │
         │  + pgvector     │
         │  + Audit Trail  │
         └────────────────┘
```

---

## Database Schema (10 Tables)

| Table | Purpose | Key Constraints |
|---|---|---|
| `orders` | Raw order records | PK: `order_id` |
| `payments` | Payment records with order FK | PK: `payment_id`, FK→`orders` |
| `settlements` | Bank settlement records | PK: `settlement_id` |
| `reconciliation_runs` | Batch run metadata (timestamps, thresholds) | PK: `run_id` |
| `reconciliation_results` | Individual match results | FK→`runs`, **UNIQUE(`payment_id`)**, **UNIQUE(`settlement_id`)** |
| `exceptions` | Unmatched/ambiguous cases with reason codes | FK→`runs`, status enum |
| `policies` | Financial policies with vector embeddings | PK: `policy_id`, `vector(256)` column |
| `agent_runs` | LangGraph agent investigation records | FK→`exceptions` |
| `agent_tool_calls` | Individual tool call traces with latency | FK→`agent_runs` |
| `human_reviews` | Operator approval/rejection audit log | FK→`exceptions` |

**Critical integrity constraints**:
- `UNIQUE(payment_id)` on `reconciliation_results` → prevents double-claiming a payment
- `UNIQUE(settlement_id)` on `reconciliation_results` → prevents double-claiming a settlement
- These are the **database-level enforcement** of the single-claim safety invariant

---

## 🎤 Probable Interview Questions

### Q: "Walk me through the architecture of your system."
**A:** "It's a 6-layer architecture. At the bottom, PostgreSQL stores all financial data. Above it, a scoring layer normalises messy input data and computes weighted match scores across 4 dimensions. A safety layer sits in the middle as a mandatory checkpoint — every match must pass 6 mathematical invariants before it can commit. The agent layer handles ambiguous cases using a LangGraph state machine that retrieves financial policies and uses sandboxed arithmetic tools. At the top, a FastAPI REST API and Streamlit dashboard serve the system to users. The key insight is the two-speed design: clean matches fly through the deterministic fast path at 5,000 rec/sec, while ambiguous cases get deep agent investigation."

### Q: "Why do you have a separate safety layer instead of building it into the scorer?"
**A:** "Separation of concerns, and defence in depth. The scorer's job is to estimate confidence — it's allowed to be wrong. The safety validator's job is to prevent catastrophic errors — it must never let through a mathematically invalid match. By separating them, the scorer can be tuned aggressively (lower thresholds, higher recall) without risking safety. The safety layer catches edge cases the scorer might miss: double-claims, temporal impossibilities, or amount conservation violations. In financial systems, you want multiple independent barriers."

### Q: "How does data flow from raw CSV to a committed match?"
**A:** "A payment record from CSV goes through: (1) Normalisation — dirty reference strings, currency symbols, and date formats are canonicalised. (2) Candidate generation — we find all settlements within a 7-day window. (3) Scoring — each candidate gets a weighted score from reference similarity, amount compatibility, date proximity, and currency match. (4) Routing — high scores auto-resolve, medium scores go to the LangGraph agent, low scores become exceptions. (5) Safety validation — the proposed match must pass 6 invariants. (6) Database commit — the result is written with ACID guarantees and the payment/settlement are marked as claimed."

### Q: "Why 10 database tables? Isn't that complex?"
**A:** "Each table serves a distinct purpose in the audit trail. Financial systems require complete traceability: you need to know not just the final match, but *when* the reconciliation ran (runs table), *what* the agent investigated (agent_runs, agent_tool_calls), *why* a case was escalated (exceptions), and *who* approved it (human_reviews). If an auditor asks 'why was payment X matched to settlement Y?', I can trace every step. The complexity is justified by regulatory requirements."
