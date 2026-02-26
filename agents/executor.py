from __future__ import annotations

import requests
from typing import Any, Dict, Tuple


def call_mcp_tool(
    tool: str,
    payload: Dict[str, Any],
    token: str,
    base_url: str,
    mtls_client_cert: Tuple[str, str],
    ca_cert: str,
) -> Dict[str, Any]:
    url = f"{base_url}/mcp/tool/{tool}"
    r = requests.post(
        url,
        json={"query": payload.get("query", "")},   # ← make sure this is here
        cert=mtls_client_cert,
        verify=ca_cert,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()