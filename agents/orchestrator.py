"""Agent orchestrator: plan -> call MCP tools over mTLS -> verify each result.

python -m agents.orchestrator "How should an MCP server enforce zero egress?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from agents.planner import plan
from agents.verifier import Verdict, verify
from mcp_server.tls import CertPaths, client_ssl_context


@dataclass
class StepResult:
    tool: str
    verdict: Verdict
    result: dict[str, Any] | None


def mtls_http_client(certs: CertPaths, token: str) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(verify=client_ssl_context(certs), headers={"Authorization": f"Bearer {token}"}, timeout=30)


async def run(task: str, url: str, certs: CertPaths, token: str) -> list[StepResult]:
    results: list[StepResult] = []
    async with mtls_http_client(certs, token) as http, Client(streamable_http_client(url, http_client=http)) as client:
        for step in plan(task):
            res = await client.call_tool(step.tool, step.arguments)
            structured = res.structured_content if isinstance(res.structured_content, dict) else None
            results.append(StepResult(step.tool, verify(step.tool, structured, bool(res.is_error)), structured))
            if not results[-1].verdict.ok:
                break  # stop the plan on the first failed verification
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", nargs="?", default="How should an MCP server enforce zero egress in GovCloud?")
    parser.add_argument("--url", default=os.getenv("MCP_URL", "https://localhost:8443/mcp"))
    parser.add_argument("--certs", default=os.getenv("CERT_DIR", "certs"))
    parser.add_argument("--token", default=os.getenv("AGENT_TOKEN", "dev-research-token"))
    args = parser.parse_args()
    for r in asyncio.run(run(args.task, args.url, CertPaths.under(args.certs), args.token)):
        print(f"[{r.tool}] {'PASS' if r.verdict.ok else 'FAIL'}: {r.verdict.reason}")
        if r.tool == "rag_answer" and r.result:
            print(json.dumps({k: r.result[k] for k in ("answer", "citations")}, indent=2))
        elif r.tool == "audit_status" and r.result:
            print(json.dumps(asdict(r.verdict) | {"records": r.result["records"]}, indent=2))


if __name__ == "__main__":
    main()
