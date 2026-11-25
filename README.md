# GovCloud-Style MCP Agent Platform

![CI](https://github.com/mostafaamer1234/govcloud-mcp-agent/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A **Model Context Protocol (MCP) tool server** for regulated environments. An agent reaches grounded-retrieval tools only through **mutual TLS**, with **scoped bearer tokens**. Every decision goes to a **tamper-evident audit log**, and the process **refuses outbound network connections** that are not on an allowlist.

It is built on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (Streamable HTTP transport), so any MCP client can connect to it.

**Interactive walkthrough: [govcloud-mcp-agent.vercel.app](https://govcloud-mcp-agent.vercel.app)**. Step through real recorded requests (allowed, scope-denied, bad token, no certificate) and see each security gate and audit record. The page lives in `site/`.


```
                      TLS 1.2+, client cert REQUIRED
┌────────────────────┐  + Authorization: Bearer <token>   ┌──────────────────────────────────────────┐
│ Agent orchestrator │ ─────────────────────────────────▶ │ MCP server (Streamable HTTP)              │
│  planner           │                                    │  1. mTLS handshake (uvicorn CERT_REQUIRED)│
│  MCP client        │ ◀───────────────────────────────── │  2. token -> principal (hashed tokens)    │
│  verifier          │   structured results + citations   │  3. per-tool scope check (deny default)   │
└────────────────────┘                                    │  4. tools: search_docs, rag_answer,       │
                                                          │     audit_status                          │
                                                          │  5. zero-egress socket guard              │
                                                          │  6. hash-chained JSONL audit log          │
                                                          └──────────────────────────────────────────┘
```

## What it demonstrates

| Control | How it is enforced | Proven by |
|---|---|---|
| Only enrolled workloads can connect | uvicorn `ssl_cert_reqs=CERT_REQUIRED` with a private CA | `test_client_without_certificate_is_rejected`, `test_client_with_untrusted_certificate_is_rejected` |
| Authentication | Bearer tokens checked in constant time against SHA-256 hashes in `config/policy.yaml` | `test_invalid_token_is_rejected` (HTTP 401) |
| Least privilege | Each tool requires a scope; unlisted tools are denied for everyone | `test_scope_is_enforced_per_tool` |
| Zero egress | Every `socket.connect` outside the allowlist raises `EgressBlocked` and is audited | `test_egress_guard_blocks_outbound_and_allows_loopback` |
| Tamper-evident audit | Each record stores the hash of the previous one; arguments are stored as hashes | `test_audit_chain_detects_tampering`, `..._deleted_record` |
| Grounded answers | Answers cite numbered sources; the agent's verifier rejects uncited or out-of-range citations | `test_verifier_requires_grounded_citations`, `test_agent_answers_with_verified_citations` |
| No secrets in git | Certificates are generated at setup and git-ignored; CI fails if key material is tracked | CI `security` job |

The end-to-end tests start the real server over HTTPS in a background thread and talk to it with the real MCP client. There are no mocks at the transport layer. I also checked that the certificate tests catch a broken setup: when client certificates are not required, the two rejection tests fail.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python scripts/gen_certs.py --out certs     # throwaway CA + server + client certs (git-ignored)
python run_server.py                        # https://localhost:8443/mcp, client cert required

# in another terminal
python -m agents.orchestrator "How do workloads reach KMS without internet egress?"
```

Real output:

```text
[search_docs] PASS: 4 passages retrieved
[rag_answer] PASS: grounded in sources [1, 2]
{
  "answer": "In AWS GovCloud this is achieved by placing workloads in private subnets with no internet gateway
             and no NAT gateway, so outbound traffic can only reach destinations inside the VPC. [1] ...
             Services such as S3, KMS, Secrets Manager, CloudWatch Logs and Bedrock are reached through VPC
             endpoints (AWS PrivateLink or gateway endpoints). [2]",
  "citations": [{"id": 1, "source": "zero-egress.md", "section": "What zero egress means", "score": 8.709}, ...]
}
```

Try other identities. A read-only agent can search but is denied `rag_answer`, and the denial is audited:

```bash
AGENT_TOKEN=dev-readonly-token python -m agents.orchestrator "How do workloads reach KMS?"
# [search_docs] PASS ...   [rag_answer] FAIL: tool returned an error  (access denied: requires scope 'rag_answer')

AGENT_TOKEN=dev-auditor-token python -m agents.orchestrator "audit log status"
# [audit_status] PASS: audit chain intact
```

The three `dev-*` tokens exist for local development only. The policy file stores only their hashes.

### Docker

```bash
python scripts/gen_certs.py --out certs
docker compose up --build                       # read-only container, non-root user, zero egress
docker compose --profile opensearch up --build  # optional private OpenSearch backend
```

## Tools

| Tool | Scope | Returns |
|---|---|---|
| `search_docs(query, top_k=4)` | `search_docs` | Ranked passages with source, section and BM25 score |
| `rag_answer(query)` | `rag_answer` | Answer whose sentences cite `[n]` sources, plus the citation list and an `uncited_claims` flag |
| `audit_status(recent=10)` | `audit_status` | Whether the hash chain verifies, the record count, and recent records |

Answer generation runs inside the boundary. By default it is extractive and deterministic. Set `OLLAMA_URL` (and `OLLAMA_MODEL`) to use a local model instead, and add its host to `EGRESS_ALLOWLIST`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CERT_DIR` | `certs` | CA, server and client certificates |
| `POLICY_FILE` | `config/policy.yaml` | Token hashes, client IDs, scopes, and tool-to-scope map |
| `ZERO_EGRESS` | `1` | Install the outbound-connection guard |
| `EGRESS_ALLOWLIST` | (empty) | Comma-separated hosts or CIDRs allowed besides loopback |
| `RETRIEVAL_BACKEND` | `bm25` | `bm25` (in-process) or `opensearch` |
| `AUDIT_LOG` | `logs/audit.jsonl` | Audit log path |
| `ALLOWED_HOSTS` | `localhost:*,127.0.0.1:*,mcp-server:*` | Host header allowlist (DNS-rebinding protection) |

## Mapping to AWS GovCloud

| Here | In GovCloud |
|---|---|
| `scripts/gen_certs.py` private CA | AWS Private CA with short-lived certificates |
| uvicorn mTLS | ALB / API Gateway mutual TLS, or mTLS terminated at the task with an ACM-issued cert |
| `config/policy.yaml` hashed tokens | IdP-issued JWTs (swap `PolicyTokenVerifier` for a JWT verifier); scopes as claims |
| In-process egress guard | Private subnets, no IGW/NAT, VPC endpoints with endpoint policies |
| BM25 / OpenSearch | OpenSearch Serverless in the VPC |
| Local model via `OLLAMA_URL` | Amazon Bedrock through a VPC interface endpoint |
| Hash-chained JSONL | CloudWatch Logs → S3 with Object Lock → SIEM |

## Threat model (summary)

- **Stolen token, no certificate.** The TLS handshake fails before the token is ever read.
- **Enrolled workload with an over-reaching prompt.** Scope checks deny any tool outside the token's scopes, and the denial is audited.
- **Prompt injection that tries to exfiltrate data.** Outbound connections are refused in-process and recorded as `egress/blocked`.
- **An insider who edits the audit log.** `audit_status` and `verify_chain` report the first altered record.
- **Out of scope:** model-level jailbreak detection, rate limiting, and certificate revocation (CRL/OCSP).

## Project layout

```
mcp_server/   server.py (tools + auth), policy.py, audit.py, egress.py, retrieval.py, answer.py, tls.py
agents/       planner.py, orchestrator.py (MCP client over mTLS), verifier.py (grounding checks)
config/       policy.yaml
corpus/       markdown knowledge base used for retrieval
scripts/      gen_certs.py
tests/        unit tests + end-to-end tests against the live HTTPS server
```

## License

MIT
