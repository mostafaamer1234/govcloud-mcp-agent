
```md
# GovCloud-Style MCP Agent Platform (mTLS + RAG + Zero-Egress)

This project is a production-inspired, security-first implementation of an **MCP (Model Context Protocol) tool server** with **agentic orchestration**, **mutual TLS (mTLS)** authentication, **Retrieval-Augmented Generation (RAG)**, **zero-egress architecture assumptions**, and **compliance-grade audit logging**.

It simulates how enterprise AI systems are deployed in **regulated environments** such as **AWS GovCloud**, air-gapped VPCs, and zero-trust SaaS platforms.

---

## Key Features

- ✅ **MCP Tool Server** (FastAPI + HTTPS)
- ✅ **Agentic AI Orchestration**
- ✅ **Mutual TLS (mTLS) Authentication**
- ✅ **Zero Public Internet Egress Architecture Pattern**
- ✅ **Retrieval-Augmented Generation (RAG) Tool**
- ✅ **Structured Compliance & Audit Logging**
- ✅ **GovCloud-Compatible Architecture Mapping**
- ✅ **Deterministic, Testable Tool Contracts**

---

## 🏗 Architecture Overview

```

+------------------+             mTLS             +------------------------+
|   Agent Client   |  ------------------------>  |      MCP Tool Server   |
|  (orchestrator)  |                             |     (FastAPI + HTTPS)  |
+------------------+                             +-----------+------------+
|                                                            |
|                                                        MCP Tools
|                                                            |
v                                                            v
+---------------------+                                   +----------------------+
| Agent Planner       |                                   | search_docs Tool     |
| Tool Selection      |                                   | rag_answer Tool      |
+---------------------+                                   +----------------------+
|
v
+----------------------+
| Audit Logs (JSONL)   |
| Compliance / SIEM    |
+----------------------+

```

---

## 🔐 Security Model

This project follows a **zero-trust** and **zero-egress** design:

| Layer | Control |
|------|--------|
TLS | Mutual TLS (client + server authentication)  
Network | No public internet egress assumed  
Identity | Client certificates identify agents  
Authorization | Tool-level access control  
Auditability | Structured JSON logs per tool invocation  
Secrets | Designed to map to KMS / Secrets Manager  
Ingress | API Gateway / ALB equivalent in production  

In production (GovCloud):
- mTLS would be enforced at API Gateway / ALB
- Certificates managed by ACM Private CA
- Audit logs shipped to CloudWatch / SIEM
- OpenSearch Serverless used for RAG

---

## 🧠 Agentic AI Flow

1. **User/Task Input**
2. **Agent Planning**
3. **Tool Selection (MCP)**
4. **mTLS-secured Tool Calls**
5. **RAG-based Grounded Responses**
6. **Compliance Logging**
7. **Agent Aggregates Results**

This mirrors real **agentic AI orchestration** patterns used in enterprise automation.

---

##  Project Structure

```

govcloud-mcp-agent-platform/
├── mcp_server/
│   ├── app.py           # MCP tool server (FastAPI)
│   ├── audit.py         # Structured compliance logging
│   └── ...
├── agents/
│   ├── orchestrator.py # Agent workflow
│   ├── executor.py     # Secure tool calls (mTLS)
│   └── planner.py      # Tool selection logic
├── certs/              # mTLS certificates (CA, server, client)
├── logs/               # Audit logs (JSONL)
├── run_server.py       # Server bootstrap
└── README.md

````

---

##  Setup & Run

### 1️⃣ Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn requests pydantic
````

---

### 2️⃣ Start MCP Server (mTLS enforced)

```bash
python run_server.py
```

Expected output:

```
Uvicorn running on https://0.0.0.0:8000
```

---

### 3️⃣ Run Agent Orchestrator

```bash
python -m agents.orchestrator
```

---

## Example Outputs

### Example 1 — Empty query (baseline execution)

```
(.venv) mostafa@Mostafas-MacBook-Pro govcloud-mcp-agent-platform % python -m agents.orchestrator
search_docs => True
{'result': '[search_docs] Found secure results for: '}
---
rag_answer => True
{'result': '[rag_answer] GovCloud enforces zero-egress, private endpoints, IAM, KMS, and audit logging. | Answering: '}
---
```

### Example 2 — Full query (RAG-style grounded output)

```
(.venv) mostafa@Mostafas-MacBook-Pro govcloud-mcp-agent-platform % python -m agents.orchestrator
search_docs => True
{'result': '[search_docs] Found secure results for: How would you design MCP + RAG in GovCloud with zero egress?'}
---
rag_answer => True
{'result': '[rag_answer] GovCloud enforces zero-egress, private endpoints, IAM, KMS, and audit logging. | Answering: How would you design MCP + RAG in GovCloud with zero egress?'}
---
```

---

## 📜 Audit Logging (Compliance-Grade)

Each MCP tool call writes structured logs:

```json
{
  "correlation_id": "uuid",
  "tool": "rag_answer",
  "timestamp": 1730000000,
  "result": "...",
  "metadata": {
    "query": "How would you design MCP + RAG in GovCloud with zero egress?"
  }
}
```

This enables:

* Forensic traceability
* Regulatory audits
* SIEM ingestion
* Incident response

---

## ☁️ GovCloud Mapping

| Local Component     | GovCloud Equivalent               |
| ------------------- | --------------------------------- |
| FastAPI MCP Server  | API Gateway + Lambda              |
| mTLS                | API Gateway mTLS + ACM Private CA |
| Audit Logs          | CloudWatch + S3                   |
| RAG Store           | OpenSearch Serverless             |
| Secrets             | AWS KMS + Secrets Manager         |
| Agent Orchestration | Step Functions / ECS              |
| Ingress             | Private ALB                       |

---

## 🧪 Testability

This architecture supports:

* Deterministic tool contracts
* Agent workflow replay
* Test automation
* CI/CD validation of tool behavior

---

## 🔒 Zero-Egress Design

This platform assumes:

* No direct internet calls from agents
* All data retrieval occurs via internal tools
* External services must be proxied via private endpoints

This is mandatory in:

* GovCloud
* Air-gapped enterprise networks
* Regulated SaaS deployments

---

## Why This Matters

Modern LLM systems in regulated environments **cannot directly access the internet** and **must operate through auditable, secured toolchains**. This project demonstrates:

* How to safely expose AI capabilities
* How to control agent behavior
* How to audit AI actions
* How to deploy in compliance-heavy environments

---

## Author Notes

This project focuses on **architecture correctness**, **security posture**, and **operational realism** rather than model quality. The RAG layer is intentionally modular and can be replaced with OpenSearch Serverless + Bedrock or any GovCloud-compatible LLM runtime.

---

##  Future Enhancements

* Plug OpenSearch Serverless for real vector retrieval
* Integrate AWS Bedrock Guardrails
* Add IAM-based tool scopes
* Add multi-agent coordination
* Add CI/CD security scanning
* Add UI for live agent interaction

---

##  Summary

This repo demonstrates a **production-style agentic AI system** with:

* MCP tool servers
* mTLS security
* RAG grounding
* Zero-egress design
* Auditability
* GovCloud-compatible architecture

It reflects how **secure enterprise AI platforms** are built in real-world environments.

---

If you use or reference this project, feel free to fork and extend it.

```


