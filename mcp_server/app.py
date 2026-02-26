from fastapi import FastAPI
from mcp_server.audit import log_event

app = FastAPI()

@app.post("/mcp/tool/search_docs")
async def search_docs(payload: dict):
    query = payload.get("query", "")
    result = f"[search_docs] Found secure results for: {query}"
    log_event("search_docs", result, {"query": query})
    return {"result": result}

@app.post("/mcp/tool/rag_answer")
async def rag_answer(payload: dict):
    query = payload.get("query", "")
    # Mock RAG for now (you can plug OpenSearch later)
    context = "GovCloud enforces zero-egress, private endpoints, IAM, KMS, and audit logging."
    result = f"[rag_answer] {context} | Answering: {query}"
    log_event("rag_answer", result, {"query": query})
    return {"result": result}