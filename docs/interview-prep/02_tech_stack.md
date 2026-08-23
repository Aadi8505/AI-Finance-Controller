# 2. Tech Stack — Every Technology & Why

## Complete Technology Map

| Layer | Technology | Version | Why This Choice |
|---|---|---|---|
| **Language** | Python | 3.11 | Dominant AI/ML ecosystem; native `Decimal` for financial arithmetic; strong typing with dataclasses |
| **LLM Framework** | LangGraph | 1.2.x | Explicit state-machine control over agent flow (vs. LangChain's implicit chains); deterministic node routing; auditable step traces |
| **LLM Client** | OpenAI API via `langchain-openai` | 1.6.x | GPT-4o-mini for structured JSON output; fallback to deterministic mock when API unavailable |
| **Policy Retrieval** | Custom RAG with NumPy + scikit-learn | numpy 2.4, sklearn 1.9 | Lightweight cosine-similarity retriever; no heavyweight vector DB needed for 7 policies |
| **Database** | PostgreSQL 16 + pgvector | pg 16, pgvector 0.5 | ACID transactions for financial data; pgvector for embedding storage; industry standard |
| **ORM** | SQLAlchemy | 2.0.x | Mature Python ORM; async-capable; native PostgreSQL dialect support |
| **DB Driver** | psycopg2-binary | 2.9.x | Standard PostgreSQL adapter for Python; battle-tested in production |
| **API Framework** | FastAPI | 0.141.x | Async-first; auto-generated OpenAPI docs; Pydantic-native request/response validation |
| **API Server** | Uvicorn | 0.52.x | ASGI server; production-grade with `--reload` for development |
| **Dashboard** | Streamlit | 1.62.x | Rapid prototyping of data dashboards; native Python dataframe rendering; interactive widgets |
| **Data Processing** | Pandas | 3.0.x | CSV ingestion, dataframe manipulation, tabular display |
| **Validation** | Pydantic | 2.13.x | Strict schema enforcement for agent decisions; `Field(ge=0.0, le=1.0)` constraints |
| **Testing** | pytest | 9.1.x | Fixture-based test framework; clean parametrised tests; rich assertion introspection |
| **Containerisation** | Docker | — | PostgreSQL + pgvector runs in Docker container for local development isolation |
| **Arithmetic** | Python `decimal.Decimal` | stdlib | Exact decimal arithmetic; no floating-point rounding errors in financial calculations |

---

## Why LangGraph Over LangChain Chains?

| LangChain LCEL Chains | LangGraph StateGraph |
|---|---|
| Linear pipeline; hard to branch | Explicit directed graph with conditional edges |
| Difficult to add intermediate validation | We insert a `validate_decision` node before output |
| Agent "tools" run in an uncontrolled loop | We control exactly which tools run in which state |
| Hard to audit intermediate steps | Each node's output is recorded in typed `AgentState` |

**In our project**: The agent must follow a strict sequence: `load_context → retrieve_policies → investigate → validate`. LangGraph enforces this as a compiled state graph.

---

## Why PostgreSQL + pgvector Over a Dedicated Vector DB?

| Dedicated Vector DB (Pinecone, Weaviate) | PostgreSQL + pgvector |
|---|---|
| Extra infrastructure to manage | Single database for both relational + vector data |
| Overkill for 7 policy documents | Lightweight; embeddings stored as `vector(256)` column |
| Network latency for vector search | In-process; co-located with relational queries |
| Extra cost | Free; PostgreSQL is already in the stack |

**In our project**: We have only 7 financial policies. A full vector database is unnecessary. pgvector lets us store embeddings alongside relational transaction data in one database.

---

## Why FastAPI Over Flask/Django?

| Flask | Django | FastAPI |
|---|---|---|
| No built-in validation | Heavy ORM we don't need (we use SQLAlchemy) | Native Pydantic validation |
| Sync by default | Sync by default | Async-first with ASGI |
| Manual OpenAPI docs | DRF adds docs | Auto-generated Swagger at `/docs` |
| No type hints enforcement | No type hints | Full type-hint driven request/response |

---

## Why Streamlit Over React/Next.js Dashboard?

| React/Next.js | Streamlit |
|---|---|
| Days to build a dashboard | Hours |
| Need separate frontend repo | Single Python file |
| Need REST API integration code | Direct Python function calls |
| Better for production UIs | Perfect for ops/internal dashboards |

**Tradeoff acknowledged**: Streamlit is not suitable for customer-facing UIs. For this project (internal finance operations console), it's the right tool.

---

## Why Python `Decimal` Over `float`?

```python
# float (DANGEROUS for finance)
>>> 0.1 + 0.2
0.30000000000000004

# Decimal (EXACT)
>>> Decimal("0.1") + Decimal("0.2")
Decimal('0.3')
```

In financial systems, even ₹0.01 rounding errors accumulate into audit failures. Every monetary calculation uses `Decimal`.

---

## 🎤 Probable Interview Questions

### Q: "Why did you choose LangGraph over regular LangChain?"
**A:** "LangChain's LCEL chains are linear pipelines — they're great for simple prompt→response flows, but I needed branching control. My agent must follow a strict 4-step state machine: load context, retrieve policies, investigate, then validate. LangGraph gives me an explicit directed graph where each node is a function, edges are deterministic, and I can insert a safety validation gate before any decision is finalised. It also gives me typed state at every step, which is critical for financial auditability."

### Q: "Why PostgreSQL and not MongoDB or a NoSQL database?"
**A:** "Financial reconciliation data is inherently relational — payments reference orders, settlements reference payments, reconciliation results join both. PostgreSQL gives me ACID transactions (critical when marking a payment as 'claimed' to prevent double-allocation), foreign key constraints, and unique indexes. Plus, with pgvector, I get vector similarity search for policy RAG without needing a separate vector database. MongoDB's eventual consistency model is dangerous for financial data where double-claiming a settlement would create accounting errors."

### Q: "What would you change for production scale?"
**A:** "Three main changes: (1) **Async task queue** — replace synchronous batch processing with Celery + Redis or AWS SQS for horizontal scaling. (2) **Streaming ingestion** — replace CSV batch imports with Kafka consumers for real-time reconciliation. (3) **Connection pooling** — add PgBouncer for database connection management at high concurrency. The current architecture already separates concerns cleanly (engine, agent, API, dashboard), so each layer can scale independently."

### Q: "Why not use a pre-built matching library?"
**A:** "Pre-built fuzzy matching libraries (like `fuzzywuzzy` or `recordlinkage`) do generic string similarity. Financial reconciliation needs domain-specific logic: fee-aware amount matching, SLA-based date scoring, reference canonicalisation that strips payment prefixes. Our scorer computes 4 weighted sub-scores with financial business rules baked in. No generic library handles 'this amount is ₹20 less because of a 2% UPI MDR fee' — that requires domain knowledge."

### Q: "Why Pydantic for agent decisions?"
**A:** "LLMs output unstructured text. In financial systems, I need guaranteed structure — a confidence score between 0.0 and 1.0, an action that's exactly one of MATCH/MANUAL_REVIEW/EXCEPTION, and a non-empty evidence summary. Pydantic's `BaseModel` with `Field(ge=0.0, le=1.0)` and `Literal` types gives me runtime validation. If the LLM hallucinates a confidence of 1.5 or an invalid action, Pydantic catches it before it reaches the database."
