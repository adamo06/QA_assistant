from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain.tools import tool
from langchain_chroma import Chroma

from config import OPENAI_API_KEY
from memory.embeddings import get_embeddings_backend
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
    embeddings = get_embeddings_backend()
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
    if not OPENAI_API_KEY:
        return LocalRagAgent()

    return create_agent(
        model=build_model(),
        tools=[retrieve_context, query_business_api, business_api_summary],
        system_prompt=RAG_SYSTEM_PROMPT,
    )


class LocalRagAgent:
    def invoke(self, inputs, config=None):
        messages = inputs.get("messages", [])
        question = ""
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, dict):
                question = str(last_message.get("content", "")).strip()
            else:
                question = str(getattr(last_message, "content", "")).strip()

        vector_store = load_vector_store()
        retrieved_docs = vector_store.similarity_search(question, k=4) if question else []
        answer = self._build_answer(question, retrieved_docs)
        return {"messages": [AIMessage(content=answer)]}

    def _build_answer(self, question, retrieved_docs):
        if not retrieved_docs:
            return (
                "Mode local activé: je n'ai pas trouvé de corpus indexé exploitable. "
                "Dépose des PDF dans `data/` puis relance l'ingestion."
            )

        lines = ["Mode local activé. Voici les passages les plus proches trouvés dans le corpus:"]

        for doc in retrieved_docs[:3]:
            source_name = doc.metadata.get("source_name", "inconnue")
            page = doc.metadata.get("page", "inconnue")
            content = " ".join(doc.page_content.split())
            lines.append(f"- {source_name}, page {page}: {content[:400]}")

        lines.append("Ce mode ne génère pas de vraie réponse LLM, mais il te donne le contexte utile.")
        return "\n".join(lines)
