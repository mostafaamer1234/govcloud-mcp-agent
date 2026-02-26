from __future__ import annotations
from pydantic import BaseModel
from typing import Any, Dict


class ToolRequest(BaseModel):
    input: Dict[str, Any] = {}


class ToolResponse(BaseModel):
    result: Any