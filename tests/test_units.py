from __future__ import annotations

import json
import socket

import pytest

from agents.verifier import verify
from mcp_server import egress
from mcp_server.answer import cited_ids, extractive_answer
from mcp_server.audit import AuditLog, verify_chain
from mcp_server.policy import Policy
from mcp_server.retrieval import BM25Retriever
from tests.conftest import ROOT


@pytest.fixture
def policy() -> Policy:
    return Policy.load(ROOT / "config" / "policy.yaml")


def test_tokens_are_matched_by_hash(policy):
    assert policy.authenticate("dev-research-token").client_id == "research-agent"
    assert policy.authenticate("not-a-token") is None


def test_unlisted_tools_are_denied(policy):
    research = policy.authenticate("dev-research-token").scopes
    assert policy.is_allowed(research, "rag_answer")
    assert not policy.is_allowed(research, "audit_status")
    assert not policy.is_allowed(research | {"delete_everything"}, "delete_everything")


def test_audit_chain_detects_tampering(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(5):
        log.record(tool="search_docs", client_id="research-agent", decision="allow", args={"q": i})
    assert verify_chain(log.path).ok

    lines = log.path.read_text().splitlines()
    record = json.loads(lines[2])
    record["decision"] = "deny"  # rewrite history
    lines[2] = json.dumps(record)
    log.path.write_text("\n".join(lines) + "\n")
    report = verify_chain(log.path)
    assert not report.ok and report.broken_at == 3


def test_audit_chain_detects_deleted_record(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    for i in range(4):
        log.record(tool="t", client_id="c", decision="allow", args={"i": i})
    lines = log.path.read_text().splitlines()
    del lines[1]
    log.path.write_text("\n".join(lines) + "\n")
    assert not verify_chain(log.path).ok


def test_audit_stores_argument_hash_not_plaintext(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record(tool="rag_answer", client_id="c", decision="allow", args={"query": "classified project name"})
    assert "classified project name" not in log.path.read_text()


def test_retrieval_ranks_the_relevant_document_first():
    hits = BM25Retriever(ROOT / "corpus").search("NAT gateway internet gateway private subnets")
    assert hits and hits[0].chunk.source == "zero-egress.md"


def test_extractive_answer_cites_only_retrieved_sources():
    hits = BM25Retriever(ROOT / "corpus").search("how are private keys removed from git history")
    text = extractive_answer("how are private keys removed from git history", hits)
    assert cited_ids(text) and cited_ids(text) <= set(range(1, len(hits) + 1))


def test_egress_guard_blocks_outbound_and_allows_loopback():
    blocked: list[tuple[str, int]] = []
    was_installed = egress.is_installed()
    egress.install(on_block=lambda h, p: blocked.append((h, p)))
    try:
        with pytest.raises(egress.EgressBlocked):
            socket.create_connection(("203.0.113.10", 443), timeout=1)  # TEST-NET-3, never routable
        assert blocked == [("203.0.113.10", 443)]
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        client = socket.create_connection(server.getsockname(), timeout=1)  # loopback is allowed
        client.close()
        server.close()
    finally:
        if not was_installed:
            egress.uninstall()


@pytest.mark.parametrize(
    ("result", "ok"),
    [
        ({"answer": "Use VPC endpoints [1].", "citations": [{"id": 1}]}, True),
        ({"answer": "Use VPC endpoints.", "citations": [{"id": 1}]}, False),  # no citation
        ({"answer": "Use VPC endpoints [3].", "citations": [{"id": 1}]}, False),  # cites unretrieved source
    ],
)
def test_verifier_requires_grounded_citations(result, ok):
    assert verify("rag_answer", result, is_error=False).ok is ok
