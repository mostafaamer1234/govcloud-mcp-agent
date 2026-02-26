from __future__ import annotations

from typing import Dict, Any


def verify(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal verifier: ensure schema-like shape.
    You can make this stricter (pydantic validation, allowed keys, etc).
    """
    if "result" not in result:
        return {"ok": False, "reason": "Missing 'result' field", "raw": result}
    return {"ok": True, "raw": result}