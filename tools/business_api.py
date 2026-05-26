import json
from time import perf_counter

from langchain.tools import tool

from api.client import get_business_api_client
from monitoring import log_request


@tool(response_format="content_and_artifact")
def query_business_api(query: str):
    """Interroge l'API métier pour récupérer des informations opérationnelles."""
    start = perf_counter()
    client = get_business_api_client()
    result = client.search(query=query, k=4)
    payload = result.payload
    elapsed_ms = (perf_counter() - start) * 1000
    log_request(request_type="business_search", latency_ms=elapsed_ms)

    lines = [
        f"Statut: {payload.get('status', 'inconnu')}",
        f"Requête: {payload.get('query', query)}",
        f"Correspondances: {payload.get('match_count', 0)}",
    ]
    for item in payload.get("matches", []):
        metadata = item.get("metadata", {})
        lines.append(
            "Source: {source_name} | page: {page} | score: {score}".format(
                source_name=metadata.get("source_name", "inconnue"),
                page=metadata.get("page", "inconnue"),
                score=item.get("score", "n/a"),
            )
        )
        snippet = item.get("content", "").strip()
        if snippet:
            lines.append(f"Extrait: {snippet[:500]}")

    return "\n".join(lines).strip(), payload


@tool
def business_api_summary() -> str:
    """Récupère un résumé du corpus indexé via l'API métier."""
    start = perf_counter()
    client = get_business_api_client()
    payload = client.summary().payload
    elapsed_ms = (perf_counter() - start) * 1000
    log_request(request_type="business_summary", latency_ms=elapsed_ms)
    return json.dumps(payload, ensure_ascii=True)
