"""Local retrieval over a markdown corpus (BM25), with an optional OpenSearch backend.

The default backend runs fully in-process, so the server works with zero egress
and no extra infrastructure. Set RETRIEVAL_BACKEND=opensearch to query a private
OpenSearch domain instead (OpenSearch Serverless inside a VPC in production).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "be",
    "with",
    "how",
    "what",
    "why",
    "do",
    "does",
    "should",
    "would",
    "you",
    "it",
    "that",
    "this",
    "by",
    "as",
}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    section: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def chunk_markdown(path: Path) -> list[Chunk]:
    """Split a markdown file into one chunk per heading section."""
    chunks: list[Chunk] = []
    section, buf = path.stem, []

    def flush() -> None:
        body = " ".join(" ".join(buf).split())
        if body:
            chunks.append(Chunk(f"{path.stem}#{len(chunks) + 1}", path.name, section, body))

    for line in path.read_text().splitlines():
        if line.startswith("#"):
            flush()
            buf = []
            section = line.lstrip("#").strip()
        else:
            buf.append(line)
    flush()
    return chunks


class BM25Retriever:
    def __init__(self, corpus_dir: str | Path):
        self.chunks: list[Chunk] = []
        for path in sorted(Path(corpus_dir).glob("*.md")):
            self.chunks.extend(chunk_markdown(path))
        if not self.chunks:
            raise ValueError(f"no markdown documents found in {corpus_dir}")
        self._bm25 = BM25Okapi([tokenize(f"{c.section} {c.text}") for c in self.chunks])

    def search(self, query: str, top_k: int = 4) -> list[Hit]:
        terms = tokenize(query)
        if not terms:
            return []
        scores = self._bm25.get_scores(terms)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        return [Hit(self.chunks[i], float(scores[i])) for i in ranked[:top_k] if scores[i] > 0]


class OpenSearchRetriever:
    def __init__(self, url: str, index: str):
        self.url, self.index = url.rstrip("/"), index

    def search(self, query: str, top_k: int = 4) -> list[Hit]:
        resp = httpx.post(
            f"{self.url}/{self.index}/_search",
            json={"size": top_k, "query": {"multi_match": {"query": query, "fields": ["section^2", "text"]}}},
            timeout=5,
        )
        resp.raise_for_status()
        hits = []
        for h in resp.json().get("hits", {}).get("hits", []):
            src = h.get("_source", {})
            chunk = Chunk(h.get("_id", ""), src.get("source", ""), src.get("section", ""), src.get("text", ""))
            hits.append(Hit(chunk, float(h.get("_score") or 0.0)))
        return hits


def build_retriever(corpus_dir: str | Path) -> BM25Retriever | OpenSearchRetriever:
    if os.getenv("RETRIEVAL_BACKEND", "bm25") == "opensearch":
        return OpenSearchRetriever(os.getenv("OPENSEARCH_URL", "http://localhost:9200"), os.getenv("OPENSEARCH_INDEX", "docs"))
    return BM25Retriever(corpus_dir)
