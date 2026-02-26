# mcp_server/audit.py
import json
import time
import uuid
from pathlib import Path

LOG_FILE = Path("logs/audit.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log_event(tool_name: str, result: str, metadata: dict | None = None):
    event = {
        "correlation_id": str(uuid.uuid4()),
        "tool": tool_name,
        "timestamp": time.time(),
        "result": result,
        "metadata": metadata or {}
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")