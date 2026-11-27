"""End-to-end tests against the real server over HTTPS with client certificates required."""

from __future__ import annotations

import ssl

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from agents.orchestrator import mtls_http_client, run
from mcp_server.audit import verify_chain
from mcp_server.tls import CertPaths

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_agent_answers_with_verified_citations(live_server, certs):
    results = await run("How do workloads reach KMS without internet egress?", live_server["url"], certs, "dev-research-token")
    assert [r.tool for r in results] == ["search_docs", "rag_answer"]
    assert all(r.verdict.ok for r in results), [r.verdict for r in results]
    assert results[1].result["generator"] == "extractive"
    assert results[1].result["uncited_claims"] is False


async def test_scope_is_enforced_per_tool(live_server, certs):
    async with mtls_http_client(certs, "dev-readonly-token") as http, Client(streamable_http_client(live_server["url"], http_client=http)) as c:
        allowed = await c.call_tool("search_docs", {"query": "audit log"})
        denied = await c.call_tool("rag_answer", {"query": "audit log"})
    assert not allowed.is_error
    assert denied.is_error and "access denied" in denied.content[0].text


async def test_audit_trail_is_intact_and_readable_by_auditor_only(live_server, certs):
    async with mtls_http_client(certs, "dev-auditor-token") as http, Client(streamable_http_client(live_server["url"], http_client=http)) as c:
        status = await c.call_tool("audit_status", {"recent": 50})
    assert not status.is_error
    data = status.structured_content
    assert data["chain_ok"] and data["records"] >= 1
    assert {r["decision"] for r in data["recent"]} >= {"allow"}
    assert verify_chain(live_server["audit_path"]).ok


async def test_invalid_token_is_rejected(live_server, certs):
    async with mtls_http_client(certs, "stolen-or-guessed-token") as http:
        resp = await http.post(
            live_server["url"], json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers={"Accept": "application/json, text/event-stream"}
        )
    assert resp.status_code == 401


async def test_client_without_certificate_is_rejected(live_server, certs):
    no_cert = ssl.create_default_context(cafile=str(certs.ca))  # trusts the server, presents no client cert
    with pytest.raises((httpx2.ConnectError, httpx2.ReadError, httpx2.RemoteProtocolError)):
        async with httpx2.AsyncClient(verify=no_cert, headers={"Authorization": "Bearer dev-research-token"}) as http:
            await http.post(live_server["url"], json={"jsonrpc": "2.0", "id": 1, "method": "ping"})


async def test_client_with_untrusted_certificate_is_rejected(live_server, certs):
    rogue = CertPaths(certs.ca, certs.server_cert, certs.server_key, certs.ca.parent / "rogue_client.crt", certs.ca.parent / "rogue_client.key")
    with pytest.raises((httpx2.ConnectError, httpx2.ReadError, httpx2.RemoteProtocolError)):
        async with mtls_http_client(rogue, "dev-research-token") as http:
            await http.post(live_server["url"], json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
