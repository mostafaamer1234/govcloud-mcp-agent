from __future__ import annotations

import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()

USE_OPENSEARCH = os.getenv("USE_OPENSEARCH", "0") == "1"
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "docs")

# Fast fallback for tonight (works without OpenSearch):
DOCS = [
    "GovCloud deployments typically enforce zero public internet egress.",
    "MCP servers expose tool providers with token-scoped access and audit logging.",
    "Least privilege IAM + KMS-backed secrets are common compliance requirements.",
    "Structured logs with correlation IDs help create compliance-ready audit trails.",
    "Agentic systems often implement planner/executor/verifier patterns with guardrails.",
]


def search_docs_mock(query: str) -> List[str]:
    q = query.lower().strip()
    if not q:
        return DOCS[:3]
    return [d for d in DOCS if q in d.lower()] or DOCS[:2]


def _opensearch_search(query: str) -> List[Dict[str, Any]]:
    # Minimal, "good enough" OpenSearch query for a demo
    r = requests.get(
        f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search",
        json={"query": {"multi_match": {"query": query, "fields": ["text"]}}},
        timeout=5,
    )
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    return [{"score": h.get("_score"), "text": h.get("_source", {}).get("text")} for h in hits]


def rag_answer(query: str) -> str:
    if USE_OPENSEARCH:
        try:
            hits = _opensearch_search(query)
            context = [h["text"] for h in hits[:3] if h.get("text")]
        except Exception:
            context = search_docs_mock(query)
    else:
        context = search_docs_mock(query)

    # Tonight: keep the "LLM" deterministic (you can swap in Ollama/OpenAI later)
    return (
        "Grounded answer:\n"
        f"- Query: {query}\n"
        f"- Retrieved context: {context}\n"
        "Conclusion: Build the system with zero-egress, mTLS, token-scoped tools, and audit logging."
    )