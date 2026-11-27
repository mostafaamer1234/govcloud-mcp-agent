"""Tamper-evident audit log.

Every tool decision (allow, deny, error) is appended as one JSON line. Each record
carries the SHA-256 of the previous record, so editing or deleting any line breaks
the chain and `verify_chain` reports where. Tool arguments are stored as a hash,
not in clear text, so the log itself never becomes a secondary data store.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENESIS = "0" * 64


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def hash_args(args: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(args).encode()).hexdigest()


@dataclass
class ChainReport:
    ok: bool
    records: int
    broken_at: int | None = None  # 1-based line number of the first bad record
    reason: str | None = None


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._read_last_hash()

    def _read_last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = GENESIS
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    last = json.loads(line)["hash"]
        return last

    def record(
        self,
        *,
        tool: str,
        client_id: str | None,
        decision: str,
        args: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        detail: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            body = {
                "ts": time.time(),
                "correlation_id": correlation_id or str(uuid.uuid4()),
                "tool": tool,
                "client_id": client_id,
                "decision": decision,
                "args_sha256": hash_args(args or {}),
                "latency_ms": None if latency_ms is None else round(latency_ms, 2),
                "detail": detail,
                "prev_hash": self._last_hash,
            }
            body["hash"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
            with self.path.open("a") as f:
                f.write(_canonical(body) + "\n")
            self._last_hash = body["hash"]
            return body

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = [ln for ln in self.path.read_text().splitlines() if ln.strip()]
        return [json.loads(ln) for ln in lines[-n:]]


def verify_chain(path: str | Path) -> ChainReport:
    path = Path(path)
    if not path.exists():
        return ChainReport(ok=True, records=0)
    prev = GENESIS
    count = 0
    with path.open() as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            count += 1
            rec = json.loads(line)
            claimed = rec.pop("hash", None)
            if rec.get("prev_hash") != prev:
                return ChainReport(False, count, lineno, "prev_hash does not match previous record")
            if hashlib.sha256(_canonical(rec).encode()).hexdigest() != claimed:
                return ChainReport(False, count, lineno, "record contents were modified")
            prev = claimed
    return ChainReport(ok=True, records=count)
