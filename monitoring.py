from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from threading import Lock


_lock = Lock()

metrics: dict[str, object] = {
    "total_requests": 0,
    "errors": 0,
    "fallbacks": 0,
    "retrieval_calls": 0,
    "empty_retrievals": 0,
    "auth_failures": 0,
    "latence_totale": 0.0,
    "retrieval_latence_totale": 0.0,
    "generation_latence_totale": 0.0,
    "tokens_in_total": 0,
    "tokens_out_total": 0,
    "tokens_total": 0,
    "cout_total": 0.0,
    "source_citation_total": 0,
    "search_score_total": 0.0,
    "search_score_count": 0,
    "ingestion_page_count": 0,
    "chunk_count": 0,
    "embedding_count": 0,
    "embedding_dimensions": 0,
    "source_count": 0,
    "stored_chunks": 0,
    "last_ingestion_timestamp": None,
    "request_types": Counter(),
    "error_types": Counter(),
}


def _estimate_cost(tokens_in: int = 0, tokens_out: int = 0) -> float:
    # Approximation simple, proche du screenshot.
    return ((tokens_in * 2.5) + (tokens_out * 10)) / 1_000_000


def log_request(
    request_type: str = "question",
    latency_ms: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    error: str | None = None,
    fallback: bool = False,
    retrieval_latency_ms: float = 0.0,
    generation_latency_ms: float = 0.0,
    source_cited: bool = False,
    retrieval_score: float | None = None,
) -> None:
    cost = _estimate_cost(tokens_in=tokens_in, tokens_out=tokens_out)
    with _lock:
        metrics["total_requests"] += 1
        metrics["latence_totale"] += latency_ms
        metrics["retrieval_latence_totale"] += retrieval_latency_ms
        metrics["generation_latence_totale"] += generation_latency_ms
        metrics["tokens_in_total"] += tokens_in
        metrics["tokens_out_total"] += tokens_out
        metrics["tokens_total"] += tokens_in + tokens_out
        metrics["cout_total"] += cost
        metrics["request_types"][request_type] += 1

        if error:
            metrics["errors"] += 1
            metrics["error_types"][error] += 1
        if fallback:
            metrics["fallbacks"] += 1
        if source_cited:
            metrics["source_citation_total"] += 1
        if retrieval_score is not None:
            metrics["search_score_total"] += retrieval_score
            metrics["search_score_count"] += 1


def log_retrieval(
    retrieval_latency_ms: float,
    hits: int,
    retrieval_score: float | None = None,
) -> None:
    with _lock:
        metrics["retrieval_calls"] += 1
        metrics["retrieval_latence_totale"] += retrieval_latency_ms
        if hits <= 0:
            metrics["empty_retrievals"] += 1
        if retrieval_score is not None:
            metrics["search_score_total"] += retrieval_score
            metrics["search_score_count"] += 1


def log_ingestion(summary: dict[str, object]) -> None:
    vectorstore = summary.get("vectorstore") or {}
    with _lock:
        metrics["ingestion_page_count"] = int(summary.get("page_count") or 0)
        metrics["chunk_count"] = int(summary.get("chunk_count") or 0)
        metrics["embedding_count"] = int(summary.get("embedding_count") or 0)
        metrics["embedding_dimensions"] = int(summary.get("embedding_dimensions") or 0)
        metrics["stored_chunks"] = int(vectorstore.get("stored_count") or 0)
        metrics["source_count"] = len(summary.get("ingested_files") or [])
        metrics["last_ingestion_timestamp"] = datetime.now(timezone.utc).isoformat()


def log_auth_failure() -> None:
    with _lock:
        metrics["auth_failures"] += 1


def get_dashboard() -> dict[str, object]:
    with _lock:
        total = int(metrics["total_requests"]) or 1
        retrieval_calls = int(metrics["retrieval_calls"]) or 1
        search_score_count = int(metrics["search_score_count"]) or 1

        return {
            "total_requests": int(metrics["total_requests"]),
            "errors": int(metrics["errors"]),
            "taux_erreur": f"{(metrics['errors'] / total) * 100:.1f}%",
            "fallbacks": int(metrics["fallbacks"]),
            "fallback_rate": f"{(metrics['fallbacks'] / total) * 100:.1f}%",
            "retrieval_calls": int(metrics["retrieval_calls"]),
            "empty_retrievals": int(metrics["empty_retrievals"]),
            "empty_retrieval_rate": f"{(metrics['empty_retrievals'] / retrieval_calls) * 100:.1f}%",
            "latence_moy_ms": round(metrics["latence_totale"] / total, 2),
            "retrieval_latence_moy_ms": round(metrics["retrieval_latence_totale"] / retrieval_calls, 2),
            "generation_latence_moy_ms": round(metrics["generation_latence_totale"] / total, 2),
            "tokens_in_total": int(metrics["tokens_in_total"]),
            "tokens_out_total": int(metrics["tokens_out_total"]),
            "tokens_total": int(metrics["tokens_total"]),
            "cout_total": f"{metrics['cout_total']:.2f} $",
            "cout_moy_request": f"{(metrics['cout_total'] / total):.6f} $",
            "cout_moy_token": f"{(metrics['cout_total'] / max(int(metrics['tokens_total']), 1)):.8f} $",
            "source_coverage_rate": f"{(metrics['source_citation_total'] / total) * 100:.1f}%",
            "mean_similarity_score": round(metrics["search_score_total"] / search_score_count, 4),
            "ingestion_page_count": int(metrics["ingestion_page_count"]),
            "chunk_count": int(metrics["chunk_count"]),
            "embedding_count": int(metrics["embedding_count"]),
            "embedding_dimensions": int(metrics["embedding_dimensions"]),
            "source_count": int(metrics["source_count"]),
            "stored_chunks": int(metrics["stored_chunks"]),
            "last_ingestion_timestamp": metrics["last_ingestion_timestamp"],
            "auth_failures": int(metrics["auth_failures"]),
            "request_types": dict(metrics["request_types"]),
            "error_types": dict(metrics["error_types"]),
        }
