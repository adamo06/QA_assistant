from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi.testclient import TestClient

from config import BUSINESS_API_BASE_URL, load_env_file


load_env_file()


@dataclass(slots=True)
class BusinessApiResult:
    payload: dict[str, Any]


class BusinessApiClient:
    def __init__(self) -> None:
        from api.server import app

        self._client = TestClient(app, base_url=BUSINESS_API_BASE_URL)

    def health(self) -> BusinessApiResult:
        response = self._client.get("/health")
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def summary(self) -> BusinessApiResult:
        response = self._client.get("/v1/business/summary")
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def search(self, query: str, k: int = 4) -> BusinessApiResult:
        response = self._client.get(
            "/v1/business/search",
            params={"q": query, "k": k},
        )
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        thread_id: str | None = None,
    ) -> BusinessApiResult:
        response = self._client.post(
            "/chat",
            json={
                "message": message,
                "history": history or [],
                "thread_id": thread_id,
            },
        )
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())


@lru_cache(maxsize=1)
def get_business_api_client() -> BusinessApiClient:
    return BusinessApiClient()
