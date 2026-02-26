from __future__ import annotations

from agents.planner import plan
from agents.executor import call_mcp_tool
from agents.verifier import verify

BASE_URL = "https://localhost:8000"

# mTLS client identity
CLIENT_CERT = ("certs/client/client.crt", "certs/client/client.key")
CA_CERT = "certs/ca/ca.crt"

# token scopes in .env must include tools used by the plan
TOKEN = "scoped-agent-token"


def run(task: str):
    steps = plan(task)
    outputs = []
    for step in steps:
        tool = step["tool"]
        payload = step["input"]
        res = call_mcp_tool(
            tool=tool,
            payload=payload,
            token=TOKEN,
            base_url=BASE_URL,
            mtls_client_cert=CLIENT_CERT,
            ca_cert=CA_CERT,
        )
        outputs.append({"tool": tool, "verified": verify(res)})
    return outputs


if __name__ == "__main__":
    out = run("How would you design MCP + RAG in GovCloud with zero egress?")
    for item in out:
        print(item["tool"], "=>", item["verified"]["ok"])
        print(item["verified"]["raw"])
        print("---")