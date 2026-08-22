"""Policy Knowledge Base RAG Retriever.

Adapted from reference-repo/src/policy_rag.py.

Embeds accounting and settlement policy passages, caches dense vectors to disk (.npy),
and performs cosine similarity search so the investigation agent can ground decisions
in written policy and cite specific policy IDs (e.g. POL_001).
"""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from app.core.model import embed_texts

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(BASE_DIR, "data", "policies")
KB_PATH = os.path.join(DATA_DIR, "knowledge_base.jsonl")
EMB_CACHE = os.path.join(DATA_DIR, "kb_embeddings.npy")


def _normalize(m: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(m, axis=-1, keepdims=True) + 1e-9
    return m / norm


class PolicyKnowledgeBaseIndex:
    """In-memory cosine similarity search over cached policy embeddings."""

    def __init__(self, kb_path: str = KB_PATH, emb_cache: str = EMB_CACHE) -> None:
        self.kb_path = kb_path
        self.emb_cache = emb_cache
        self.docs = self._load_docs()
        self.vecs = _normalize(self._embed_all())

    def _load_docs(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.kb_path):
            raise FileNotFoundError(f"Knowledge base not found at: {self.kb_path}")
        docs = []
        with open(self.kb_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    docs.append(json.loads(line))
        return docs

    def _embed_all(self) -> np.ndarray:
        texts = [f"{d['title']}. {d['text']}" for d in self.docs]
        probe_dim = len(embed_texts(["probe"])[0])

        if os.path.exists(self.emb_cache):
            try:
                cached = np.load(self.emb_cache)
                if cached.shape[0] == len(texts) and cached.shape[1] == probe_dim:
                    return cached
            except Exception:
                pass

        vecs = np.asarray(embed_texts(texts), dtype="float32")
        os.makedirs(os.path.dirname(self.emb_cache), exist_ok=True)
        np.save(self.emb_cache, vecs)
        return vecs

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Retrieve top_k most relevant policy passages with similarity scores."""
        if not query.strip():
            return self.docs[:top_k]

        qv = _normalize(np.asarray(embed_texts([query]), dtype="float32"))[0]
        sims = self.vecs @ qv
        top_indices = np.argsort(-sims)[:top_k]

        results = []
        for idx in top_indices:
            doc = dict(self.docs[idx])
            doc["similarity_score"] = round(float(sims[idx]), 4)
            results.append(doc)

        return results

    def __len__(self) -> int:
        return len(self.docs)


# Global singleton instance
_kb_index: PolicyKnowledgeBaseIndex | None = None


def get_policy_kb() -> PolicyKnowledgeBaseIndex:
    global _kb_index
    if _kb_index is None:
        _kb_index = PolicyKnowledgeBaseIndex()
    return _kb_index


def search_policies(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Public helper function for agent and tools."""
    kb = get_policy_kb()
    return kb.search(query, top_k=top_k)
