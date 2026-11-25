"""Token and tool authorization policy.

The policy file maps bearer tokens (stored only as SHA-256 hashes) to a client
identity and a set of scopes, and maps each MCP tool to the scope it requires.
Tools that are not listed are denied by default.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Principal:
    client_id: str
    scopes: frozenset[str]


@dataclass
class Policy:
    principals: dict[str, Principal] = field(default_factory=dict)  # token sha256 -> principal
    tool_scopes: dict[str, str] = field(default_factory=dict)  # tool name -> required scope

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        raw = yaml.safe_load(Path(path).read_text()) or {}
        principals = {entry["token_sha256"].lower(): Principal(entry["client_id"], frozenset(entry.get("scopes", []))) for entry in raw.get("tokens", [])}
        tool_scopes = {name: spec["scope"] for name, spec in (raw.get("tools") or {}).items()}
        return cls(principals, tool_scopes)

    def authenticate(self, token: str) -> Principal | None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        for known, principal in self.principals.items():
            if hmac.compare_digest(known, digest):
                return principal
        return None

    def required_scope(self, tool: str) -> str | None:
        return self.tool_scopes.get(tool)

    def is_allowed(self, scopes: set[str] | frozenset[str], tool: str) -> bool:
        needed = self.required_scope(tool)
        return needed is not None and needed in scopes
