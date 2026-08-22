-- =============================================================================
-- AI FINANCE CONTROLLER DATABASE SCHEMA (PostgreSQL + pgvector)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Orders
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    order_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PAID',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Payments
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL REFERENCES orders(order_id),
    amount NUMERIC(14, 2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_method VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
    raw_reference TEXT NOT NULL,
    canonical_reference VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_payments_canonical_ref ON payments(canonical_reference);

-- 3. Settlements
CREATE TABLE IF NOT EXISTS settlements (
    settlement_id VARCHAR(64) PRIMARY KEY,
    payment_reference TEXT NOT NULL,
    canonical_reference VARCHAR(64) NOT NULL,
    gross_amount NUMERIC(14, 2) NOT NULL,
    fee NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    refund NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    net_amount NUMERIC(14, 2) NOT NULL,
    settlement_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'SETTLED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_settlements_canonical_ref ON settlements(canonical_reference);
CREATE INDEX IF NOT EXISTS idx_settlements_date ON settlements(settlement_date);

-- 4. Reconciliation Runs
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    total_processed INT NOT NULL,
    auto_resolved_count INT NOT NULL,
    exception_count INT NOT NULL,
    elapsed_seconds NUMERIC(10, 4) NOT NULL,
    t_high NUMERIC(5, 4) NOT NULL DEFAULT 0.90,
    t_low NUMERIC(5, 4) NOT NULL DEFAULT 0.50,
    status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Reconciliation Results (Matched items)
CREATE TABLE IF NOT EXISTS reconciliation_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES reconciliation_runs(run_id) ON DELETE CASCADE,
    payment_id VARCHAR(64) NOT NULL REFERENCES payments(payment_id),
    settlement_id VARCHAR(64) NOT NULL REFERENCES settlements(settlement_id),
    amount_paid NUMERIC(14, 2) NOT NULL,
    settlement_net NUMERIC(14, 2) NOT NULL,
    fee_deducted NUMERIC(14, 2) NOT NULL,
    discrepancy NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    confidence_score NUMERIC(5, 4) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'AUTO_RESOLVED',
    audit_note TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_payment_reconciled UNIQUE (payment_id),
    CONSTRAINT uq_settlement_reconciled UNIQUE (settlement_id)
);

-- 6. Exceptions
CREATE TABLE IF NOT EXISTS exceptions (
    exception_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) REFERENCES reconciliation_runs(run_id) ON DELETE SET NULL,
    payment_id VARCHAR(64) NOT NULL REFERENCES payments(payment_id),
    amount NUMERIC(14, 2) NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
    description TEXT NOT NULL,
    candidate_settlement_ids JSONB DEFAULT '[]'::jsonb,
    suggested_action VARCHAR(64) NOT NULL DEFAULT 'INVESTIGATE_AGENT',
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- OPEN, RESOLVED, REJECTED
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exceptions_reason ON exceptions(reason_code);
CREATE INDEX IF NOT EXISTS idx_exceptions_status ON exceptions(status);

-- 7. Policy Knowledge Base (with pgvector support)
CREATE TABLE IF NOT EXISTS policies (
    policy_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    category VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(256), -- Default 256 for mock / adaptable to 1536 for OpenAI
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Agent Runs & Tool Calls (Full execution observability)
CREATE TABLE IF NOT EXISTS agent_runs (
    agent_run_id VARCHAR(64) PRIMARY KEY,
    payment_id VARCHAR(64) NOT NULL REFERENCES payments(payment_id),
    action VARCHAR(32) NOT NULL, -- MATCH, MANUAL_REVIEW, EXCEPTION
    confidence NUMERIC(5, 4) NOT NULL,
    applied_policy_id VARCHAR(64) REFERENCES policies(policy_id),
    reason_codes JSONB DEFAULT '[]'::jsonb,
    evidence_summary TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    call_id VARCHAR(64) PRIMARY KEY,
    agent_run_id VARCHAR(64) NOT NULL REFERENCES agent_runs(agent_run_id) ON DELETE CASCADE,
    tool_name VARCHAR(64) NOT NULL,
    tool_input JSONB NOT NULL,
    tool_output JSONB NOT NULL,
    execution_time_ms NUMERIC(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Human Reviews
CREATE TABLE IF NOT EXISTS human_reviews (
    review_id VARCHAR(64) PRIMARY KEY,
    exception_id VARCHAR(64) NOT NULL REFERENCES exceptions(exception_id),
    reviewer_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL, -- APPROVE_MATCH, REJECT, ESCALATE
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
