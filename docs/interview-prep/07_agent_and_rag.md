# 7. LangGraph Agent & Policy RAG

## Part A: Why An Agent?

The deterministic scorer handles 80% of records. The remaining 20% are cases where:
- Fee deductions need policy verification (is 2.3% valid for a UPI transaction?)
- Multiple candidates have similar scores (conflicting duplicates)
- Settlement timing is borderline (T+4 during holidays — is that acceptable?)

These require **reasoning**: consulting policies, doing arithmetic, and making a judgement. That's what the LangGraph agent does.

---

## Part B: LangGraph State Machine Architecture

### File: `backend/app/agents/graph/reconciliation_graph.py`

The agent is a **4-node directed graph** (not a free-form chat loop):

```
load_context → retrieve_policies → investigate_and_reason → validate_decision → END
```

### Node 1: `load_context`
- **Input**: Payment ID + list of candidate settlements
- **Action**: Runs the weighted scorer on all candidates, prunes to top 5 by score
- **Output**: Enriched state with scored candidates and match reasons

### Node 2: `retrieve_policies`
- **Input**: Payment details and candidate characteristics
- **Action**: Queries the Policy RAG retriever with a natural language question
  - Example: "What is the fee policy for UPI payments?"
  - Returns top-2 most relevant policies by cosine similarity
- **Output**: Retrieved policy texts added to state

### Node 3: `investigate_and_reason`
- **Input**: Full context — payment, candidates, policies, tool results
- **Action**: 
  - Constructs a detailed prompt with all evidence
  - Calls LLM (or deterministic mock) to produce a structured `AgentDecision`
  - Decision includes: action, confidence, applied policy, reason codes, evidence
- **Output**: `AgentDecision` Pydantic object

### Node 4: `validate_decision`
- **Input**: The agent's proposed decision
- **Action**: Passes the decision through the Safety Validator
  - If action is "MATCH": validates all 6 invariants
  - If action is "MANUAL_REVIEW" or "EXCEPTION": directly accepted
- **Output**: Final status (AUTO_RESOLVED, MANUAL_REVIEW, EXCEPTION) + audit note

### Why a State Machine and Not a ReAct Loop?

| ReAct Agent (LangChain) | Our StateGraph |
|---|---|
| LLM decides which tool to call next | Graph enforces exact sequence |
| Can loop infinitely | Fixed 4-node pipeline, always terminates |
| Tool calls are unpredictable | We control exactly what runs when |
| Hard to guarantee safety validation | Safety validation is a mandatory node |
| Non-deterministic execution path | Deterministic, auditable path |

In financial systems, we need **guaranteed termination** and **mandatory safety checks**. A ReAct agent could skip validation if the LLM decides to return early.

---

## Part C: Structured Agent Output (Pydantic Schema)

### File: `backend/app/agents/schemas/decision.py`

```python
class AgentDecision(BaseModel):
    payment_id: str
    settlement_id: Optional[str] = None    # null if no match
    action: Literal["MATCH", "MANUAL_REVIEW", "EXCEPTION"]
    confidence: float = Field(ge=0.0, le=1.0)  # strict range
    applied_policy_id: Optional[str] = None     # e.g. "POL_002"
    reason_codes: list[str] = []                # e.g. ["FEE_WITHIN_RANGE"]
    evidence_summary: str                       # human-readable explanation
```

**Why Pydantic?**: The LLM must return JSON conforming to this exact schema. Pydantic validates at runtime — if the LLM outputs `confidence: 1.5` or `action: "APPROVE"`, validation fails and the case is safely routed to manual review.

---

## Part D: Sandboxed Financial Tools

### File: `backend/app/agents/tools/financial_tools.py`

**Critical design principle**: The LLM is **never allowed to do arithmetic**. All math is done by pure Python tools.

### Tool 1: `calculate_fee_difference`
```python
def calculate_fee_difference(payment_amount, settlement_net, payment_method):
    """Pure Decimal arithmetic — LLM cannot do this."""
    fee_deducted = Decimal(str(payment_amount)) - Decimal(str(settlement_net))
    fee_pct = (fee_deducted / Decimal(str(payment_amount))) * 100
    
    # Check against standard fee schedules
    expected_ranges = {
        "UPI":       (Decimal("0.0"), Decimal("1.2")),
        "CARD":      (Decimal("1.5"), Decimal("2.5")),
        "NETBANKING":(Decimal("1.0"), Decimal("2.0")),
    }
    min_fee, max_fee = expected_ranges.get(payment_method, (0, 3))
    is_valid = min_fee <= fee_pct <= max_fee
    
    return {
        "fee_deducted": str(fee_deducted),
        "fee_percentage": str(fee_pct),
        "is_within_expected_range": is_valid,
        "expected_range": f"{min_fee}% - {max_fee}%"
    }
```

### Tool 2: `verify_settlement_window`
```python
def verify_settlement_window(payment_date, settlement_date):
    """Calendar arithmetic for SLA verification."""
    delta_days = (settlement_date - payment_date).days
    within_sla = 0 <= delta_days <= 4  # Standard T+2 with buffer
    
    return {
        "delta_days": delta_days,
        "within_standard_sla": within_sla,
        "assessment": "NORMAL" if delta_days <= 2 else 
                      "ACCEPTABLE" if delta_days <= 4 else "EXCESSIVE"
    }
```

### Tool 3 & 4: Database Query Tools
```python
def get_payment_details(payment_id): ...    # Read-only DB query
def get_settlement_details(settlement_id): ... # Read-only DB query
```

### Tool Registry & Dispatch
```python
# Every tool call is timed and traced
def dispatch_tool_call(tool_name, arguments):
    start = time.perf_counter()
    result = registry[tool_name](**arguments)
    elapsed = time.perf_counter() - start
    return ToolTrace(tool_name, arguments, result, elapsed_ms)
```

---

## Part E: Policy RAG Retriever

### File: `backend/app/rag/retriever.py`

### Knowledge Base: `data/policies/knowledge_base.jsonl`

7 financial policies as structured documents:

| Policy ID | Title | Key Content |
|---|---|---|
| POL_001 | Settlement Timing SLA | T+2 standard, up to T+4 for holidays |
| POL_002 | UPI Fee Schedule | 0% for <₹2000, 0.5%–1.1% for larger |
| POL_003 | Card Processing Fees | 1.5%–2.5% MDR for credit/debit cards |
| POL_004 | Netbanking/Wallet Fees | 1.0%–2.0% processing fee |
| POL_005 | Duplicate Escalation | 2+ candidates with similar scores → MANUAL_REVIEW |
| POL_006 | Partial Settlement | 10%–20% rolling reserve holdback policy |
| POL_007 | Refund/Chargeback | Deductions and reversal rules |

### How Retrieval Works

```
1. Each policy text is embedded into a 256-dim vector (via text-embedding model or TF-IDF fallback)
2. Embeddings are L2-normalised and cached to disk (kb_embeddings.npy)
3. At query time:
   a. Embed the query string
   b. Compute cosine similarity against all 7 policy embeddings
   c. Return top-K policies by similarity score
4. The agent receives the full policy text as grounding context
```

### Why Not Use the LLM's Training Data Instead?

The LLM's training data may contain generic financial knowledge, but **our policies are specific to this platform**. For example, POL_005 says "When 2+ candidates have matching amounts, always escalate to MANUAL_REVIEW" — this is a business rule, not general knowledge. RAG ensures the agent's decisions are grounded in **our written policies**, not hallucinated "common sense."

---

## Part F: The Mock Reasoner

When no OpenAI API key is available, the agent uses a deterministic mock that implements the same decision tree:

```python
def _mock_investigation_logic(data):
    candidates = data["candidates"]
    
    if len(candidates) == 0:
        return EXCEPTION with reason "NO_CANDIDATES"
    
    if len(candidates) >= 2 and scores are close:
        return MANUAL_REVIEW with reason "CONFLICTING_DUPLICATE" 
        and policy "POL_005"
    
    best = candidates[0]
    fee_result = calculate_fee_difference(...)
    
    if fee_result["is_within_expected_range"]:
        return MATCH with reason "FEE_WITHIN_RANGE" 
        and policy "POL_002" or "POL_003"
    
    return MANUAL_REVIEW with reason "FEE_OUTSIDE_RANGE"
```

This is **not a shortcut** — it follows the same logic path a well-prompted LLM would, but deterministically. Tests verify the mock produces the same quality decisions.

---

## 🎤 Probable Interview Questions

### Q: "Why can't the LLM do the arithmetic itself?"
**A:** "LLMs are unreliable at precise arithmetic. GPT-4 will sometimes compute 1000 - 980 as 21 instead of 20. In financial systems, that error means flagging a valid 2.0% fee as invalid (2.1%). By sandboxing all arithmetic into Python Decimal tools, I guarantee bit-exact correctness. The LLM's job is reasoning and decision-making — 'given that the fee is 2.0% and the policy allows 1.5%–2.5%, this is a valid match.' The math itself is never delegated to the LLM."

### Q: "How does the RAG retriever work?"
**A:** "It's a lightweight cosine similarity retriever. The 7 financial policies are embedded into 256-dimensional vectors using a text embedding model (with a TF-IDF fallback for offline use). When the agent needs policy guidance, it formulates a natural language query like 'fee policy for card payments'. I embed the query, compute cosine similarity against all 7 policy embeddings, and return the top 2. The agent then uses the full policy text as grounding context for its decision. Embeddings are cached to disk to avoid recomputation."

### Q: "What's the advantage of using a state machine vs. a free-form agent?"
**A:** "Predictability and safety. A free-form ReAct agent might call tools in any order, loop indefinitely, or skip validation. My 4-node StateGraph enforces a strict sequence: load context, retrieve policies, investigate, then validate. The safety validation node is **mandatory** — it can't be skipped regardless of what the LLM generates. This is critical in finance where every decision must pass through deterministic safety checks before committing."

### Q: "How do you handle LLM failures?"
**A:** "Three layers of resilience: (1) The deterministic mock works without any API key, so the system always functions. (2) If the LLM returns malformed JSON that doesn't conform to the Pydantic schema, the parser catches it and routes the case to MANUAL_REVIEW. (3) If the LLM returns a MATCH decision that fails safety validation (e.g., amount conservation violation), the validator overrides it and routes to MANUAL_REVIEW. The system never propagates an LLM error to the database."

### Q: "What does 'grounded' mean in the context of your RAG?"
**A:** "It means the agent's decisions are based on retrieved written policies, not on the LLM's pre-training knowledge. When the agent says 'this fee is valid per POL_003', it's citing a specific document it retrieved — not hallucinating a fee policy from its training data. This is auditable: the evidence summary includes the policy ID, and a human reviewer can verify the citation."
