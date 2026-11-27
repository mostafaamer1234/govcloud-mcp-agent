"""Deterministic planner: decide which MCP tools a task needs, in order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_AUDIT_WORDS = {"audit", "log", "logs", "tamper", "chain"}


@dataclass(frozen=True)
class Step:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


def plan(task: str) -> list[Step]:
    words = set(task.lower().split())
    if words & _AUDIT_WORDS and "status" in words:
        return [Step("audit_status", {"recent": 5})]
    # Retrieve first so the run log shows what evidence the answer can draw on, then answer.
    return [Step("search_docs", {"query": task, "top_k": 4}), Step("rag_answer", {"query": task})]
