from functools import lru_cache

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from llm import build_model
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
    vector_store = load_vector_store()
    retrieved_docs = vector_store.similarity_search(query, k=4)
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


def build_rag_agent():
    return create_agent(
        model=build_model(),
        tools=[retrieve_context, query_business_api, business_api_summary],
        system_prompt=RAG_SYSTEM_PROMPT,
    )
