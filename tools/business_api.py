import json

from langchain.tools import tool

from api.client import get_business_api_client


@tool(response_format="content_and_artifact")
def query_business_api(query: str):
    """Interroge l'API métier pour récupérer des informations opérationnelles."""
    client = get_business_api_client()
    result = client.search(query=query, k=4)
    payload = result.payload

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
    client = get_business_api_client()
    payload = client.summary().payload
    return json.dumps(payload, ensure_ascii=True)
