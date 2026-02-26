from __future__ import annotations

import requests

BASE_URL = "https://localhost:8000"
CLIENT_CERT = ("certs/client/client.crt", "certs/client/client.key")
CA_CERT = "certs/ca/ca.crt"


def test_search_docs():
    r = requests.post(
        f"{BASE_URL}/mcp/tool/search_docs",
        json={"input": {"query": "MCP"}},
        headers={"x-token": "test"},
        cert=CLIENT_CERT,
        verify=CA_CERT,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    assert "result" in data
    assert "hits" in data["result"]


if __name__ == "__main__":
    test_search_docs()
    print("API tests passed.")