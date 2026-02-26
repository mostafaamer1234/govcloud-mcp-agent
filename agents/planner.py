from __future__ import annotations

from typing import List, Dict, Any


def plan(task: str) -> List[Dict[str, Any]]:
    """
    Simple deterministic planner:
    - always retrieve docs
    - then produce a grounded answer
    """
    return [
        {"tool": "search_docs", "input": {"query": task}},
        {"tool": "rag_answer", "input": {"query": task}},
    ]