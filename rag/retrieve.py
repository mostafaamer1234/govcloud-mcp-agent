from __future__ import annotations

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "docs")


def search(query: str):
    r = requests.get(
        f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_search",
        json={"query": {"multi_match": {"query": query, "fields": ["text"]}}},
        timeout=5,
    )
    r.raise_for_status()
    hits = r.json().get("hits", {}).get("hits", [])
    return [h.get("_source", {}).get("text") for h in hits]