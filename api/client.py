from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi.testclient import TestClient

from config import (
    BUSINESS_API_AUTH_METHOD,
    BUSINESS_API_BASE_URL,
    BUSINESS_API_KEY,
    BUSINESS_OAUTH_CLIENT_ID,
    BUSINESS_OAUTH_CLIENT_SECRET,
    load_env_file,
)
from api.server import app


load_env_file()


@dataclass(slots=True)
class BusinessApiResult:
    payload: dict[str, Any]


class BusinessApiClient:
    def __init__(self) -> None:
        self._client = TestClient(app, base_url=BUSINESS_API_BASE_URL)
        self._bearer_token: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        if BUSINESS_API_AUTH_METHOD == "api_key":
            return {"X-API-Key": BUSINESS_API_KEY}

        if BUSINESS_API_AUTH_METHOD == "oauth":
            if not self._bearer_token:
                response = self._client.post(
                    "/oauth/token",
                    json={
                        "grant_type": "client_credentials",
                        "client_id": BUSINESS_OAUTH_CLIENT_ID,
                        "client_secret": BUSINESS_OAUTH_CLIENT_SECRET,
                    },
                )
                response.raise_for_status()
                self._bearer_token = response.json()["access_token"]
            return {"Authorization": f"Bearer {self._bearer_token}"}

        return {}

    def health(self) -> BusinessApiResult:
        response = self._client.get("/health")
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def summary(self) -> BusinessApiResult:
        response = self._client.get("/v1/business/summary", headers=self._auth_headers())
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def search(self, query: str, k: int = 4) -> BusinessApiResult:
        response = self._client.get(
            "/v1/business/search",
            params={"q": query, "k": k},
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def agent(self, instruction: str) -> BusinessApiResult:
        response = self._client.post(
            "/v1/business/agent",
            json={"instruction": instruction},
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())

    def demo_agent(self, instruction: str) -> BusinessApiResult:
        response = self._client.post(
            "/v1/demo/agent",
            json={"instruction": instruction},
        )
        response.raise_for_status()
        return BusinessApiResult(payload=response.json())


@lru_cache(maxsize=1)
def get_business_api_client() -> BusinessApiClient:
    return BusinessApiClient()
