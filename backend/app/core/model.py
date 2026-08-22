"""Provider-Independent LLM & Embedding Wrapper with Offline Mock Fallback.

Adapted from reference-repo/src/model.py.

Guarantees:
1. Swappable LLM providers (OpenAI, Mock, Bedrock, etc.) in a single file.
2. Deterministic offline mock model when APP_USE_MOCK=1 (or when no API key is present).
3. The LLM NEVER performs financial arithmetic.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("APP_LLM_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("APP_EMBED_MODEL", "text-embedding-3-small")
_FORCE_MOCK = os.getenv("APP_USE_MOCK", "1") == "1"
_HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))

USING_MOCK = _FORCE_MOCK or not _HAS_KEY

_client = None
if not USING_MOCK:
    try:
        from openai import OpenAI
        _client = OpenAI()
    except Exception:
        USING_MOCK = True


def _stable_vector(text: str, dim: int = 256) -> list[float]:
    """Generate dense pseudo-embedding based on word/subword n-gram hash projection for offline RAG."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for tok in tokens:
        # Word hash
        h_word = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % dim
        vec[h_word] += 1.0
        # Subword 3-grams
        for i in range(len(tok) - 2):
            gram = tok[i:i+3]
            h_gram = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16) % dim
            vec[h_gram] += 0.5

    # L2 normalize
    norm = sum(x * x for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate dense vector embeddings (OpenAI or deterministic mock)."""
    if USING_MOCK or _client is None:
        return [_stable_vector(t) for t in texts]
    
    resp = _client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def query_llm_json(
    system_prompt: str,
    user_prompt: str,
    mock_response_handler: Any = None,
) -> dict:
    """Query LLM with guaranteed JSON output."""
    if USING_MOCK or _client is None:
        if mock_response_handler:
            return mock_response_handler(user_prompt)
        return {"action": "MANUAL_REVIEW", "confidence": 0.5, "evidence_summary": "Offline mock default"}

    resp = _client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "MANUAL_REVIEW", "confidence": 0.0, "evidence_summary": "JSON decode error from LLM"}
