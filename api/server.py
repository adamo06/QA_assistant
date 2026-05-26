from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from secrets import token_urlsafe
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from config import (
    BUSINESS_API_AUTH_METHOD,
    BUSINESS_API_KEY,
    BUSINESS_OAUTH_CLIENT_ID,
    BUSINESS_OAUTH_CLIENT_SECRET,
    load_env_file,
)
from monitoring import get_dashboard, log_auth_failure, log_request
from memory.vectorstore import CHROMA_DIR, COLLECTION_NAME


load_env_file()

app = FastAPI(title="Business API", version="1.0.0")
TOKEN_STORE: dict[str, dict[str, Any]] = {}


class OAuthTokenRequest(BaseModel):
    grant_type: str = Field(default="client_credentials")
    client_id: str
    client_secret: str


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AgentRequest(BaseModel):
    instruction: str = Field(min_length=1)


class AgentResponse(BaseModel):
    status: str
    instruction: str
    answer: str
    metrics: dict[str, Any]


def _extract_usage_from_result(result: dict[str, Any]) -> tuple[int, int, int]:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    for message in result.get("messages", []):
        usage_metadata = getattr(message, "usage_metadata", None) or {}
        response_metadata = getattr(message, "response_metadata", None) or {}
        token_usage = response_metadata.get("token_usage") or {}

        input_tokens += int(
            usage_metadata.get("input_tokens")
            or token_usage.get("prompt_tokens")
            or 0
        )
        output_tokens += int(
            usage_metadata.get("output_tokens")
            or token_usage.get("completion_tokens")
            or 0
        )
        total_tokens += int(
            usage_metadata.get("total_tokens")
            or token_usage.get("total_tokens")
            or 0
        )

    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return input_tokens, output_tokens, total_tokens


@dataclass(slots=True)
class AuthContext:
    method: str
    principal: str


@lru_cache(maxsize=1)
def load_vector_store() -> Chroma:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
    )


def _require_auth(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    if x_api_key and x_api_key == BUSINESS_API_KEY:
        return AuthContext(method="api_key", principal="service-account")

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        token_data = TOKEN_STORE.get(token)
        if token_data and token_data["expires_at"] > datetime.now(timezone.utc):
            return AuthContext(method="oauth", principal=token_data["principal"])

    log_auth_failure()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized.",
    )


@app.middleware("http")
async def record_latency(request: Request, call_next):
    from time import perf_counter

    start = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - start) * 1000
    if request.url.path not in {"/metrics", "/health"}:
        log_request(
            request_type=f"api:{request.method}:{request.url.path}",
            latency_ms=elapsed_ms,
        )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/oauth/token", response_model=OAuthTokenResponse)
def oauth_token(payload: OAuthTokenRequest) -> OAuthTokenResponse:
    if payload.grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only client_credentials is supported.",
        )
    if (
        payload.client_id != BUSINESS_OAUTH_CLIENT_ID
        or payload.client_secret != BUSINESS_OAUTH_CLIENT_SECRET
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )

    access_token = token_urlsafe(32)
    expires_in = 3600
    TOKEN_STORE[access_token] = {
        "principal": payload.client_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    return OAuthTokenResponse(access_token=access_token, expires_in=expires_in)


@app.get("/v1/business/summary")
def business_summary() -> dict[str, Any]:
    vector_store = load_vector_store()
    stored = vector_store._collection.get() if vector_store._collection else {}
    metadata = [item for item in stored.get("metadatas", []) if item]
    sources = sorted(
        {
            item.get("source_name") or item.get("source")
            for item in metadata
            if item.get("source_name") or item.get("source")
        }
    )

    return {
        "status": "ok",
        "collection_name": COLLECTION_NAME,
        "chunk_count": vector_store._collection.count() if vector_store._collection else 0,
        "document_sources": sources,
        "source_count": len(sources),
    }


@app.get("/v1/business/search")
def business_search(
    q: str = Query(min_length=2),
    k: int = Query(default=4, ge=1, le=10),
) -> dict[str, Any]:
    vector_store = load_vector_store()
    results = vector_store.similarity_search_with_score(q, k=k)

    matches = []
    for doc, score in results:
        matches.append(
            {
                "content": doc.page_content,
                "metadata": {
                    "source": doc.metadata.get("source"),
                    "source_name": doc.metadata.get("source_name"),
                    "source_type": doc.metadata.get("source_type"),
                    "page": doc.metadata.get("page"),
                    "chunk_index": doc.metadata.get("chunk_index"),
                    "embedding_model": doc.metadata.get("embedding_model"),
                },
                "score": score,
            }
        )

    return {
        "status": "ok",
        "query": q,
        "match_count": len(matches),
        "matches": matches,
    }


@app.post("/v1/business/agent", response_model=AgentResponse)
def business_agent(
    payload: AgentRequest,
) -> AgentResponse:
    from agents.rag import build_rag_agent
    from time import perf_counter

    start = perf_counter()
    agent = build_rag_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": payload.instruction}]})
    elapsed_ms = (perf_counter() - start) * 1000

    last_message = result["messages"][-1]
    answer = getattr(last_message, "content", None)
    if not isinstance(answer, str):
        answer = str(last_message)

    tokens_in, tokens_out, tokens_total = _extract_usage_from_result(result)

    lower_answer = answer.lower()
    fallback = ("je ne peux pas" in lower_answer) or ("je n'" in lower_answer) or ("contexte" in lower_answer)
    source_cited = ("source" in lower_answer) or ("page" in lower_answer)

    log_request(
        request_type="agent_inference",
        latency_ms=elapsed_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        fallback=fallback,
        source_cited=source_cited,
    )

    return AgentResponse(
        status="ok",
        instruction=payload.instruction,
        answer=answer,
        metrics=get_dashboard(),
    )


@app.post("/v1/demo/agent", response_model=AgentResponse)
def demo_agent(payload: AgentRequest) -> AgentResponse:
    from agents.rag import build_rag_agent
    from time import perf_counter

    start = perf_counter()
    agent = build_rag_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": payload.instruction}]})
    elapsed_ms = (perf_counter() - start) * 1000

    last_message = result["messages"][-1]
    answer = getattr(last_message, "content", None)
    if not isinstance(answer, str):
        answer = str(last_message)

    tokens_in, tokens_out, tokens_total = _extract_usage_from_result(result)

    lower_answer = answer.lower()
    fallback = ("je ne peux pas" in lower_answer) or ("je n'" in lower_answer) or ("contexte" in lower_answer)
    source_cited = ("source" in lower_answer) or ("page" in lower_answer)

    log_request(
        request_type="demo_agent_inference",
        latency_ms=elapsed_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        fallback=fallback,
        source_cited=source_cited,
    )

    return AgentResponse(
        status="ok",
        instruction=payload.instruction,
        answer=answer,
        metrics=get_dashboard(),
    )


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return get_dashboard()
