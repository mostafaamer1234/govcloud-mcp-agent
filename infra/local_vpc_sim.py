from __future__ import annotations

import os
import socket


def sanity_check_zero_egress() -> None:
    """
    Quick demo check. In real environments, DNS resolution might still work
    even if internet egress is blocked—so treat this as a "demo-only" signal.
    """
    if os.getenv("ZERO_EGRESS", "0") != "1":
        print("ZERO_EGRESS is OFF")
        return

    try:
        socket.gethostbyname("google.com")
        print("DNS resolution works (this does NOT mean egress is allowed).")
    except Exception:
        print("DNS resolution blocked (stronger isolation).")