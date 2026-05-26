from collections.abc import Sequence
from pathlib import Path
import json

from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.tools import tool

from monitoring import log_ingestion
from memory.store import EmbeddedChunk, clear_documents, store_documents
from memory.vectorstore import clear_vectorstore, index_chunks_in_chroma


EMBEDDING_MODEL = "text-embedding-3-small"


def ingest_pdf_corpus_data(pdf_paths: Sequence[str]) -> dict[str, object]:
    normalized_paths = []
    for raw_path in pdf_paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            normalized_paths.extend(sorted(path.rglob("*.pdf")))
        elif path.is_file() and path.suffix.lower() == ".pdf":
            normalized_paths.append(path)

    if not normalized_paths:
        clear_documents()
        clear_vectorstore()
        return {
            "status": "error",
            "message": "No PDF files found. Provide one or more PDF files or directories.",
            "ingested_files": [],
            "page_count": 0,
            "chunk_count": 0,
        }

    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
    chunks = []
    ingested_files = []

    for pdf_path in normalized_paths:
        loader = PyPDFLoader(str(pdf_path))
        documents = loader.load()
        for document in documents:
            document.metadata["source"] = str(pdf_path)
        chunks.extend(splitter.split_documents(documents))
        ingested_files.append(str(pdf_path))

    if not chunks:
        clear_documents()
        clear_vectorstore()
        return {
            "status": "error",
            "message": "The PDFs were loaded, but no text chunks could be generated.",
            "ingested_files": ingested_files,
            "page_count": 0,
            "chunk_count": 0,
        }

    embedding_client = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    embeddings = embedding_client.embed_documents([chunk.page_content for chunk in chunks])
    store_documents(
        [
            EmbeddedChunk(document=chunk, embedding=embedding)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
    )
    vectorstore_summary = index_chunks_in_chroma(chunks, embeddings)

    unique_pages = {
        (chunk.metadata.get("source"), chunk.metadata.get("page"))
        for chunk in chunks
        if chunk.metadata.get("page") is not None
    }

    summary = {
        "status": "ok",
        "message": "PDF corpus ingested and parsed with LangChain.",
        "embedding_model": EMBEDDING_MODEL,
        "ingested_files": ingested_files,
        "page_count": len(unique_pages),
        "chunk_count": len(chunks),
        "embedding_count": len(embeddings),
        "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
        "vectorstore": vectorstore_summary,
    }
    log_ingestion(summary)
    return summary


@tool
def ingest_pdf_corpus(pdf_paths: Sequence[str]) -> str:
    """Charge et parse un corpus PDF métier avec LangChain."""
    return json.dumps(ingest_pdf_corpus_data(pdf_paths), ensure_ascii=True)
