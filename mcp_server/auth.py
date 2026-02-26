from __future__ import annotations

import os
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()


def _token_scopes_from_env(token: str) -> set[str]:
    """
    .env format:
    TOKEN_<token>=scope1,scope2
    e.g. TOKEN_scoped-agent-token=search_docs,rag_answer,get_user
    """
    key = f"TOKEN_{token}"
    raw = os.getenv(key, "")
    scopes = {s.strip() for s in raw.split(",") if s.strip()}
    return scopes


def require_token_scope(token: str, required_scope: str) -> None:
    scopes = _token_scopes_from_env(token)
    if required_scope not in scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Token missing required scope '{required_scope}'. Token scopes: {sorted(scopes)}",
        )