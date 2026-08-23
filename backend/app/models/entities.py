"""SQLAlchemy ORM Entities for the AI Finance Controller."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.database import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class OrderModel(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    customer_id = Column(String(64), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="INR")
    order_date = Column(Date, nullable=False)
    status = Column(String(32), nullable=False, default="PAID")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    payments = relationship("PaymentModel", back_populates="order")


class PaymentModel(Base):
    __tablename__ = "payments"

    payment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), ForeignKey("orders.order_id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    payment_method = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="SUCCESS")
    raw_reference = Column(Text, nullable=False)
    canonical_reference = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("OrderModel", back_populates="payments")
    reconciliation_result = relationship("ReconciliationResultModel", back_populates="payment", uselist=False)
    exceptions = relationship("ExceptionModel", back_populates="payment")


class SettlementModel(Base):
    __tablename__ = "settlements"

    settlement_id = Column(String(64), primary_key=True)
    payment_reference = Column(Text, nullable=False)
    canonical_reference = Column(String(64), nullable=False, index=True)
    gross_amount = Column(Numeric(14, 2), nullable=False)
    fee = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    refund = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    net_amount = Column(Numeric(14, 2), nullable=False)
    settlement_date = Column(Date, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="SETTLED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    reconciliation_result = relationship("ReconciliationResultModel", back_populates="settlement", uselist=False)


class ReconciliationRunModel(Base):
    __tablename__ = "reconciliation_runs"

    run_id = Column(String(64), primary_key=True)
    total_processed = Column(Integer, nullable=False)
    auto_resolved_count = Column(Integer, nullable=False)
    exception_count = Column(Integer, nullable=False)
    elapsed_seconds = Column(Numeric(10, 4), nullable=False)
    t_high = Column(Numeric(5, 4), nullable=False, default=Decimal("0.90"))
    t_low = Column(Numeric(5, 4), nullable=False, default=Decimal("0.50"))
    status = Column(String(32), nullable=False, default="COMPLETED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    results = relationship("ReconciliationResultModel", back_populates="run", cascade="all, delete-orphan")
    exceptions = relationship("ExceptionModel", back_populates="run")


class ReconciliationResultModel(Base):
    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("reconciliation_runs.run_id", ondelete="CASCADE"), nullable=False)
    payment_id = Column(String(64), ForeignKey("payments.payment_id"), nullable=False, unique=True)
    settlement_id = Column(String(64), ForeignKey("settlements.settlement_id"), nullable=False, unique=True)
    amount_paid = Column(Numeric(14, 2), nullable=False)
    settlement_net = Column(Numeric(14, 2), nullable=False)
    fee_deducted = Column(Numeric(14, 2), nullable=False)
    discrepancy = Column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    confidence_score = Column(Numeric(5, 4), nullable=False)
    status = Column(String(32), nullable=False, default="AUTO_RESOLVED")
    audit_note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    run = relationship("ReconciliationRunModel", back_populates="results")
    payment = relationship("PaymentModel", back_populates="reconciliation_result")
    settlement = relationship("SettlementModel", back_populates="reconciliation_result")


class ExceptionModel(Base):
    __tablename__ = "exceptions"

    exception_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("reconciliation_runs.run_id", ondelete="SET NULL"), nullable=True)
    payment_id = Column(String(64), ForeignKey("payments.payment_id"), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    reason_code = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="MEDIUM")
    description = Column(Text, nullable=False)
    candidate_settlement_ids = Column(JSONType, default=list)
    suggested_action = Column(String(64), nullable=False, default="INVESTIGATE_AGENT")
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    metadata_json = Column("metadata", JSONType, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    run = relationship("ReconciliationRunModel", back_populates="exceptions")
    payment = relationship("PaymentModel", back_populates="exceptions")
    reviews = relationship("HumanReviewModel", back_populates="exception")


class PolicyModel(Base):
    __tablename__ = "policies"

    policy_id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    category = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    # vector column mapped dynamically in pgvector
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    agent_run_id = Column(String(64), primary_key=True)
    payment_id = Column(String(64), ForeignKey("payments.payment_id"), nullable=False)
    action = Column(String(32), nullable=False)
    confidence = Column(Numeric(5, 4), nullable=False)
    applied_policy_id = Column(String(64), ForeignKey("policies.policy_id"), nullable=True)
    reason_codes = Column(JSONType, default=list)
    evidence_summary = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    tool_calls = relationship("AgentToolCallModel", back_populates="agent_run", cascade="all, delete-orphan")


class AgentToolCallModel(Base):
    __tablename__ = "agent_tool_calls"

    call_id = Column(String(64), primary_key=True)
    agent_run_id = Column(String(64), ForeignKey("agent_runs.agent_run_id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(String(64), nullable=False)
    tool_input = Column(JSONType, nullable=False)
    tool_output = Column(JSONType, nullable=False)
    execution_time_ms = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    agent_run = relationship("AgentRunModel", back_populates="tool_calls")


class HumanReviewModel(Base):
    __tablename__ = "human_reviews"

    review_id = Column(String(64), primary_key=True)
    exception_id = Column(String(64), ForeignKey("exceptions.exception_id"), nullable=False)
    reviewer_id = Column(String(64), nullable=False)
    action = Column(String(32), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    exception = relationship("ExceptionModel", back_populates="reviews")
