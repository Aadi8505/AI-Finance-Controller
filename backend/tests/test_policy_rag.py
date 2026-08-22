"""Unit tests for Policy Knowledge Base RAG Retriever."""

import pytest
from app.rag.retriever import PolicyKnowledgeBaseIndex, get_policy_kb, search_policies


def test_load_knowledge_base():
    kb = get_policy_kb()
    assert len(kb) >= 5
    assert len(kb.vecs) == len(kb.docs)


def test_search_settlement_timing_policy():
    results = search_policies("What is the standard settlement delay SLA in days?", top_k=2)
    assert len(results) >= 1
    doc_ids = [d["doc_id"] for d in results]
    assert "POL_001" in doc_ids or "POL_006" in doc_ids
    assert "similarity_score" in results[0]


def test_search_fee_policy():
    results = search_policies("card processing fee percentage", top_k=2)
    assert len(results) >= 1
    doc_ids = [d["doc_id"] for d in results]
    assert "POL_003" in doc_ids or "POL_002" in doc_ids or "POL_004" in doc_ids


def test_search_duplicate_conflict_policy():
    results = search_policies("multiple conflicting duplicate settlement candidates", top_k=2)
    assert len(results) >= 1
    doc_ids = [d["doc_id"] for d in results]
    assert "POL_005" in doc_ids
