"""Export the corpus and authorization policy for the browser console (site/corpus.json, site/policy.json).

The console runs the same pipeline as mcp_server/ in the browser: token check against the
policy's SHA-256 hashes, per-tool scopes, BM25 retrieval over heading-sized chunks, the
extractive answerer, the verifier and a hash-chained audit log.

    python scripts/export_site.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    docs = [{"name": p.name, "text": p.read_text()} for p in sorted((ROOT / "corpus").glob("*.md"))]
    raw = yaml.safe_load((ROOT / "config" / "policy.yaml").read_text())
    policy = {
        "tokens": [{"client_id": t["client_id"], "token_sha256": t["token_sha256"], "scopes": t.get("scopes", [])} for t in raw["tokens"]],
        "tools": {name: spec["scope"] for name, spec in raw["tools"].items()},
    }
    (ROOT / "site" / "corpus.json").write_text(json.dumps(docs, indent=1))
    (ROOT / "site" / "policy.json").write_text(json.dumps(policy, indent=1))
    print(len(docs), "documents,", len(policy["tokens"]), "tokens")


if __name__ == "__main__":
    main()
