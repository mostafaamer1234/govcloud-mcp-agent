from __future__ import annotations

"""
Tonight-friendly "Playwright style" test.
If you want real Playwright UI tests, add a tiny frontend and run actual browser automation.
This file is structured to demonstrate the same test discipline: dynamic calls, structured assertions.
"""

import requests

BASE_URL = "https://localhost:8000"
CLIENT_CERT = ("certs/client/client.crt", "certs/client/client.key")
CA_CERT = "certs/ca/ca.crt"


def test_rag_answer():
    r = requests.post(
        f"{BASE_URL}/mcp/tool/rag_answer",
        json={"input": {"query": "zero egress"}},
        headers={"x-token": "scoped-agent-token"},
        cert=CLIENT_CERT,
        verify=CA_CERT,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    assert "result" in data
    assert "answer" in data["result"]
    assert "Grounded answer" in data["result"]["answer"]


if __name__ == "__main__":
    test_rag_answer()
    print("Playwright-style test passed.")