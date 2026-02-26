from __future__ import annotations

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "docs")


DOCS = [
    {"id": "1", "text": "GovCloud requires zero public internet egress and private endpoints."},
    {"id": "2", "text": "MCP tools should be token-scoped and protected with mTLS, with audit logging."},
    {"id": "3", "text": "OpenSearch is commonly used for RAG retrieval in AWS-compatible environments."},
]


def create_index():
    # Very simple mapping
    requests.put(f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}", json={"mappings": {"properties": {"text": {"type": "text"}}}}, timeout=5)


def ingest():
    for d in DOCS:
        requests.put(f"{OPENSEARCH_URL}/{OPENSEARCH_INDEX}/_doc/{d['id']}", json=d, timeout=5)


if __name__ == "__main__":
    create_index()
    ingest()
    print("Ingested docs into OpenSearch.")