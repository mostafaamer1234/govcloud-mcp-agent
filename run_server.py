"""Start the MCP server over HTTPS with client certificates required.

python scripts/gen_certs.py --out certs
python run_server.py
"""

from __future__ import annotations

import os

import uvicorn
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.server import create_server
from mcp_server.tls import CertPaths, uvicorn_ssl_kwargs


def build_app(server_url: str):
    allowed = [h for h in os.getenv("ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,mcp-server:*").split(",") if h]
    mcp = create_server(server_url=server_url)
    return mcp.streamable_http_app(
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=allowed),
    )


if __name__ == "__main__":
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8443"))
    certs = CertPaths.under(os.getenv("CERT_DIR", "certs"))
    uvicorn.run(build_app(f"https://localhost:{port}"), host=host, port=port, **uvicorn_ssl_kwargs(certs))
