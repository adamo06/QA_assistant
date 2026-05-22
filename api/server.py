from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field
from langchain_chroma import Chroma

from config import load_env_file
from agents.rag import build_rag_agent
from memory.embeddings import get_embeddings_backend
from memory.vectorstore import CHROMA_DIR, COLLECTION_NAME


load_env_file()

app = FastAPI(title="Business API", version="1.0.0")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    status: str
    answer: str
    thread_id: str | None = None


@lru_cache(maxsize=1)
def load_vector_store() -> Chroma:
    embeddings = get_embeddings_backend()
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
    )


@lru_cache(maxsize=1)
def load_rag_agent():
    return build_rag_agent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


def _extract_answer_text(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return ""

    last_message = messages[-1]
    content = getattr(last_message, "content", None)
    if isinstance(content, str):
        return content.strip()

    content_blocks = getattr(last_message, "content_blocks", None)
    if content_blocks:
        parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
            else:
                block_type = getattr(block, "type", None)
                block_text = getattr(block, "text", None)
                if block_type == "text" and block_text:
                    parts.append(block_text)
        return "\n".join(parts).strip()

    return str(last_message)


@app.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
) -> ChatResponse:
    agent = load_rag_agent()
    messages: list[dict[str, str]] = [
        {"role": item.role, "content": item.content} for item in payload.history
    ]
    messages.append({"role": "user", "content": payload.message})

    invoke_config: dict[str, Any] = {}
    if payload.thread_id:
        invoke_config["configurable"] = {"thread_id": payload.thread_id}

    result = agent.invoke({"messages": messages}, config=invoke_config or None)
    answer = _extract_answer_text(result)

    return ChatResponse(
        status="ok",
        answer=answer,
        thread_id=payload.thread_id,
    )
