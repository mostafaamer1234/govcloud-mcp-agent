"""TLS settings for mutual authentication."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CertPaths:
    ca: Path
    server_cert: Path
    server_key: Path
    client_cert: Path
    client_key: Path

    @classmethod
    def under(cls, root: str | Path) -> CertPaths:
        r = Path(root)
        return cls(r / "ca.crt", r / "server.crt", r / "server.key", r / "client.crt", r / "client.key")


def uvicorn_ssl_kwargs(certs: CertPaths) -> dict[str, object]:
    """Keyword arguments that make uvicorn require and verify a client certificate."""
    return {
        "ssl_certfile": str(certs.server_cert),
        "ssl_keyfile": str(certs.server_key),
        "ssl_ca_certs": str(certs.ca),
        "ssl_cert_reqs": ssl.CERT_REQUIRED,  # without this, uvicorn accepts clients with no certificate
    }


def client_ssl_context(certs: CertPaths) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(certs.ca))
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(certs.client_cert), str(certs.client_key))
    return ctx
