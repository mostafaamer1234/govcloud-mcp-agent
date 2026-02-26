from __future__ import annotations

from rag.ingest import create_index, ingest

if __name__ == "__main__":
    create_index()
    ingest()
    print("Index created + documents ingested.")