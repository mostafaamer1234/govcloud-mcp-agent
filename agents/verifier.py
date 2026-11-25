"""Verifier: reject tool results that are malformed or not grounded in retrieved sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_CITE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class Verdict:
    ok: bool
    reason: str


def verify(tool: str, result: dict[str, Any] | None, is_error: bool) -> Verdict:
    if is_error:
        return Verdict(False, "tool returned an error")
    if not isinstance(result, dict):
        return Verdict(False, "missing structured result")
    if tool == "search_docs":
        if not result.get("hits"):
            return Verdict(False, "no documents matched")
        return Verdict(True, f"{len(result['hits'])} passages retrieved")
    if tool == "rag_answer":
        answer = result.get("answer", "")
        retrieved = {c["id"] for c in result.get("citations", [])}
        cited = {int(n) for n in _CITE.findall(answer)}
        if not cited:
            return Verdict(False, "answer contains no citations")
        if cited - retrieved:
            return Verdict(False, f"answer cites sources that were not retrieved: {sorted(cited - retrieved)}")
        return Verdict(True, f"grounded in sources {sorted(cited)}")
    if tool == "audit_status":
        return Verdict(bool(result.get("chain_ok")), "audit chain intact" if result.get("chain_ok") else "audit chain broken")
    return Verdict(False, f"no verifier for tool {tool!r}")
