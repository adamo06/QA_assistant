from functools import lru_cache
from time import perf_counter

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from llm import build_model
from monitoring import log_retrieval, log_request
from memory.vectorstore import CHROMA_DIR, COLLECTION_NAME
from tools.business_api import business_api_summary, query_business_api


RAG_SYSTEM_PROMPT = """Tu es un assistant de recherche documentaire métier.

Règles:
- Réponds uniquement à partir du contexte récupéré dans la base vectorielle.
- Si le contexte ne suffit pas, dis-le clairement.
- Cite les sources sous la forme: source_name, page.
- Réponds en français, de manière concise et utile.
- Tu peux aussi utiliser l'API métier pour obtenir un résumé du corpus ou des extraits pertinents.
"""


@lru_cache(maxsize=1)
def load_vector_store() -> Chroma:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
    )


@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Récupère le contexte pertinent du corpus PDF indexé."""
    start = perf_counter()
    vector_store = load_vector_store()
    retrieved_docs = vector_store.similarity_search(query, k=4)
    elapsed_ms = (perf_counter() - start) * 1000
    log_retrieval(elapsed_ms, len(retrieved_docs))
    serialized = "\n\n".join(
        (
            "Source: {source_name} | page: {page}\n"
            "Contenu: {content}"
        ).format(
            source_name=doc.metadata.get("source_name", "inconnue"),
            page=doc.metadata.get("page", "inconnue"),
            content=doc.page_content,
        )
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs


@tool
def log_answer_stats(
    latency_ms: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
    fallback: bool = False,
    source_cited: bool = False,
) -> str:
    """Enregistre des métriques de réponse après génération."""
    log_request(
        request_type="rag_answer",
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        fallback=fallback,
        source_cited=source_cited,
    )
    return "ok"


def build_rag_agent():
    return create_agent(
        model=build_model(),
        tools=[retrieve_context, query_business_api, business_api_summary, log_answer_stats],
        system_prompt=RAG_SYSTEM_PROMPT,
    )
