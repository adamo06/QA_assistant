from __future__ import annotations

import math
import re
from collections.abc import Sequence
from hashlib import sha256
from typing import Protocol

from langchain_openai import OpenAIEmbeddings


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_DIMENSIONS = 384


class EmbeddingsBackend(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class LocalHashEmbeddings:
    """Deterministic local fallback for similarity search without an API key."""

    def __init__(self, dimensions: int = LOCAL_EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    def _vectorize(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = sha256(token.encode("utf-8", errors="ignore")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = -1.0 if digest[4] & 1 else 1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)


def get_embeddings_backend():
    """Return the OpenAI embeddings backend when available, otherwise a local fallback."""
    from config import OPENAI_API_KEY

    if OPENAI_API_KEY:
        return OpenAIEmbeddings(model=DEFAULT_EMBEDDING_MODEL)
    return LocalHashEmbeddings()
