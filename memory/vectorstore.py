from hashlib import sha1
import json
from pathlib import Path

import chromadb
from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "pdf_corpus"
EMBEDDING_MODEL = "text-embedding-3-small"
REQUIRED_METADATA_KEYS = {
    "source",
    "source_name",
    "source_type",
    "page",
    "chunk_index",
    "chunk_id",
    "chunk_chars",
    "embedding_model",
}


def _clean_metadata_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_chunk_metadata(
    document: Document,
    chunk_index: int,
    embedding_model: str = EMBEDDING_MODEL,
) -> dict[str, object]:
    source = _clean_metadata_value(document.metadata.get("source", "unknown"))
    source_path = Path(str(source))
    page = document.metadata.get("page")
    page_number = int(page) if isinstance(page, int) else -1
    chunk_text = document.page_content or ""
    chunk_id = sha1(
        f"{source}|{page_number}|{chunk_index}|{chunk_text}".encode("utf-8", errors="ignore")
    ).hexdigest()

    return {
        "source": str(source),
        "source_name": source_path.name if source_path.name else str(source),
        "source_type": "pdf",
        "page": page_number,
        "chunk_index": chunk_index,
        "chunk_id": chunk_id,
        "chunk_chars": len(chunk_text),
        "embedding_model": embedding_model,
    }


def index_chunks_in_chroma(
    documents: list[Document],
    embeddings: list[list[float]],
    embedding_model: str = EMBEDDING_MODEL,
) -> dict[str, object]:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict[str, object]] = []

    for chunk_index, (document, embedding) in enumerate(zip(documents, embeddings, strict=True)):
        metadata = build_chunk_metadata(document, chunk_index, embedding_model=embedding_model)
        ids.append(metadata["chunk_id"])
        texts.append(document.page_content)
        metadatas.append(metadata)

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    stored = collection.get()
    stored_metadatas = [metadata for metadata in stored.get("metadatas", []) if metadata]
    metadata_keys = sorted({key for metadata in stored_metadatas for key in metadata.keys()})
    missing_required_keys = sorted(
        key for key in REQUIRED_METADATA_KEYS if key not in metadata_keys
    )
    sample_metadata = stored_metadatas[0] if stored_metadatas else {}

    return {
        "collection_name": COLLECTION_NAME,
        "chroma_dir": str(CHROMA_DIR),
        "stored_count": collection.count(),
        "metadata_keys": metadata_keys,
        "required_metadata_keys": sorted(REQUIRED_METADATA_KEYS),
        "missing_required_keys": missing_required_keys,
        "sample_metadata": sample_metadata,
    }


def clear_vectorstore() -> None:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
