"""MCP server: grounded-retrieval tools behind mTLS, scoped bearer tokens, and a hash-chained audit log.

Layers of control, outermost first:
1. Transport: TLS 1.2+ with client certificates required (see `tls.py`, enforced by uvicorn).
2. Authentication: bearer token verified against hashed tokens in the policy file.
3. Authorization: every tool checks the caller's scopes against the policy (deny by default).
4. Egress: outbound sockets outside the allowlist are refused in-process (`egress.py`).
5. Audit: every allow / deny / error is appended to a tamper-evident log (`audit.py`).
"""

from __future__ import annotations

import functools
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from . import egress
from .answer import answer as generate_answer
from .answer import cited_ids
from .audit import AuditLog, verify_chain
from .policy import Policy
from .retrieval import build_retriever

ROOT = Path(__file__).resolve().parent.parent
P = ParamSpec("P")
R = TypeVar("R")


class PolicyTokenVerifier:
    """Validates bearer tokens against the hashed tokens in the policy file."""

    def __init__(self, policy: Policy):
        self.policy = policy

    async def verify_token(self, token: str) -> AccessToken | None:
        principal = self.policy.authenticate(token)
        if principal is None:
            return None
        return AccessToken(token=token, client_id=principal.client_id, scopes=sorted(principal.scopes))


class Citation(BaseModel):
    id: int
    source: str
    section: str
    score: float


class SearchResult(BaseModel):
    query: str
    hits: list[Citation]
    snippets: list[str]


class GroundedAnswer(BaseModel):
    query: str
    answer: str
    generator: str = Field(description="'extractive', 'ollama', or 'none'")
    citations: list[Citation]
    uncited_claims: bool = Field(description="True if the answer cites a source number that was not retrieved")


class AuditStatus(BaseModel):
    chain_ok: bool
    records: int
    broken_at: int | None
    recent: list[dict[str, Any]]


def create_server(
    policy_path: str | Path | None = None,
    corpus_dir: str | Path | None = None,
    audit_path: str | Path | None = None,
    server_url: str = "https://localhost:8443",
) -> MCPServer:
    policy = Policy.load(policy_path or os.getenv("POLICY_FILE", ROOT / "config" / "policy.yaml"))
    retriever = build_retriever(corpus_dir or os.getenv("CORPUS_DIR", ROOT / "corpus"))
    audit = AuditLog(audit_path or os.getenv("AUDIT_LOG", ROOT / "logs" / "audit.jsonl"))

    if os.getenv("ZERO_EGRESS", "1") == "1" and not egress.is_installed():
        allow = [h for h in os.getenv("EGRESS_ALLOWLIST", "").split(",") if h]
        egress.install(allow, on_block=lambda h, p: audit.record(tool="egress", client_id=None, decision="blocked", detail=f"{h}:{p}"))

    mcp = MCPServer(
        name="govcloud-mcp-agent",
        instructions="Grounded answers over an internal compliance corpus. All calls are scoped and audited.",
        token_verifier=PolicyTokenVerifier(policy),
        auth=AuthSettings(
            issuer_url=os.getenv("AUTH_ISSUER_URL", "https://auth.internal.example"),
            resource_server_url=server_url,
            validate_token_resource=False,
        ),
    )

    def secured(tool_name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
        """Enforce the policy scope for `tool_name` and audit the outcome."""

        def decorate(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
            @functools.wraps(fn)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                token = get_access_token()
                client_id = token.client_id if token else None
                scopes = set(token.scopes) if token else set()
                cid = str(uuid.uuid4())
                if not policy.is_allowed(scopes, tool_name):
                    audit.record(
                        tool=tool_name,
                        client_id=client_id,
                        decision="deny",
                        args=dict(kwargs),
                        correlation_id=cid,
                        detail=f"requires scope {policy.required_scope(tool_name)!r}",
                    )
                    raise ToolError(f"access denied: '{tool_name}' requires scope {policy.required_scope(tool_name)!r}")
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                except Exception as exc:
                    audit.record(
                        tool=tool_name,
                        client_id=client_id,
                        decision="error",
                        args=dict(kwargs),
                        correlation_id=cid,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        detail=type(exc).__name__,
                    )
                    raise
                audit.record(
                    tool=tool_name,
                    client_id=client_id,
                    decision="allow",
                    args=dict(kwargs),
                    correlation_id=cid,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
                return result

            return wrapper

        return decorate

    @mcp.tool(description="Search the internal corpus and return ranked passages with their sources.")
    @secured("search_docs")
    async def search_docs(query: str, top_k: int = 4) -> SearchResult:
        hits = retriever.search(query, top_k=max(1, min(top_k, 10)))
        return SearchResult(
            query=query,
            hits=[Citation(id=i, source=h.chunk.source, section=h.chunk.section, score=round(h.score, 3)) for i, h in enumerate(hits, 1)],
            snippets=[h.chunk.text for h in hits],
        )

    @mcp.tool(description="Answer a question using only retrieved passages; every claim cites a numbered source.")
    @secured("rag_answer")
    async def rag_answer(query: str) -> GroundedAnswer:
        hits = retriever.search(query, top_k=4)
        text, generator = generate_answer(query, hits)
        citations = [Citation(id=i, source=h.chunk.source, section=h.chunk.section, score=round(h.score, 3)) for i, h in enumerate(hits, 1)]
        return GroundedAnswer(
            query=query,
            answer=text,
            generator=generator,
            citations=citations,
            uncited_claims=bool(cited_ids(text) - {c.id for c in citations}),
        )

    @mcp.tool(description="Verify the audit log hash chain and return the most recent records.")
    @secured("audit_status")
    async def audit_status(recent: int = 10) -> AuditStatus:
        report = verify_chain(audit.path)
        return AuditStatus(chain_ok=report.ok, records=report.records, broken_at=report.broken_at, recent=audit.tail(max(0, min(recent, 100))))

    mcp.audit_log = audit  # type: ignore[attr-defined]  # exposed for tests and the CLI
    return mcp
