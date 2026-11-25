"""Zero-egress guard.

In a real GovCloud VPC, egress is blocked by the network (no NAT gateway, no
internet gateway, VPC endpoints only). This module enforces the same rule inside
the process so a mis-configured dependency or a prompt-injected tool cannot open
an outbound connection: every socket connect is checked against an allowlist.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable

_original_connect = socket.socket.connect
_original_create_connection = socket.create_connection
_installed = False


class EgressBlocked(ConnectionRefusedError):
    pass


def _host_allowed(host: str, allow: set[str]) -> bool:
    if host in allow:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.is_loopback:
        return True
    return any(_in_network(ip, entry) for entry in allow)


def _in_network(ip: ipaddress._BaseAddress, entry: str) -> bool:
    try:
        return ip in ipaddress.ip_network(entry, strict=False)
    except ValueError:
        return False


def install(allow: Iterable[str] = (), on_block: Callable[[str, int], None] | None = None) -> None:
    """Block outbound connections to anything outside `allow` (loopback is always allowed)."""
    global _installed
    allowed = {a.strip() for a in allow if a.strip()} | {"localhost"}

    def check(address: object) -> None:
        if not isinstance(address, tuple) or len(address) < 2:
            return  # unix sockets etc. are local by definition
        host, port = str(address[0]), int(address[1])
        if not _host_allowed(host, allowed):
            if on_block:
                on_block(host, port)
            raise EgressBlocked(f"zero-egress policy blocked connection to {host}:{port}")

    def guarded_connect(self: socket.socket, address: object) -> None:
        check(address)
        return _original_connect(self, address)

    def guarded_create_connection(address: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
        check(address)
        return _original_create_connection(address, *args, **kwargs)

    socket.socket.connect = guarded_connect  # type: ignore[method-assign]
    socket.create_connection = guarded_create_connection  # type: ignore[assignment]
    _installed = True


def uninstall() -> None:
    global _installed
    socket.socket.connect = _original_connect  # type: ignore[method-assign]
    socket.create_connection = _original_create_connection  # type: ignore[assignment]
    _installed = False


def is_installed() -> bool:
    return _installed
