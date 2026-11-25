from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def certs(tmp_path_factory):
    from mcp_server.tls import CertPaths
    from scripts.gen_certs import generate

    out = generate(tmp_path_factory.mktemp("certs"))
    return CertPaths.under(out)


@pytest.fixture(scope="session")
def live_server(certs, tmp_path_factory):
    """Run the real server over HTTPS with client certificates required, in a background thread."""
    from mcp.server.transport_security import TransportSecuritySettings

    from mcp_server.server import create_server
    from mcp_server.tls import uvicorn_ssl_kwargs

    os.environ["ZERO_EGRESS"] = "1"
    port = _free_port()
    audit_path = tmp_path_factory.mktemp("audit") / "audit.jsonl"
    mcp = create_server(audit_path=audit_path, server_url=f"https://localhost:{port}")
    app = mcp.streamable_http_app(transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=[f"localhost:{port}"]))
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", **uvicorn_ssl_kwargs(certs))
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("server did not start")
        time.sleep(0.05)
    yield {"url": f"https://localhost:{port}/mcp", "audit_path": audit_path}
    server.should_exit = True
    thread.join(timeout=5)
