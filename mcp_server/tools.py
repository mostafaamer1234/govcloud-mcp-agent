from __future__ import annotations

from typing import Any, Dict
from .rag import rag_answer, search_docs_mock


def tool_search_docs(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", ""))
    hits = search_docs_mock(query)
    return {"query": query, "hits": hits}


def tool_rag_answer(payload: Dict[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query", ""))
    answer = rag_answer(query)
    return {"query": query, "answer": answer}


def tool_get_user(payload: Dict[str, Any]) -> Dict[str, Any]:
    uid = str(payload.get("user_id", "unknown"))
    return {"user_id": uid, "role": "demo-admin", "scopes": ["search_docs", "rag_answer", "get_user"]}


TOOL_REGISTRY = {
    # tool_name must match scope name in auth.py
    "search_docs": tool_search_docs,
    "rag_answer": tool_rag_answer,
    "get_user": tool_get_user,
}