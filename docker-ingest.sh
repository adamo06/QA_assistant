#!/bin/sh
set -eu

PDF_CORPUS_PATHS_VALUE="${PDF_CORPUS_PATHS:-/app/data}"

echo "Ingestion du corpus depuis ${PDF_CORPUS_PATHS_VALUE}"
PDF_CORPUS_PATHS="${PDF_CORPUS_PATHS_VALUE}" python - <<'PY'
import os
from tools.search import ingest_pdf_corpus_data

raw_paths = os.getenv("PDF_CORPUS_PATHS", "/app/data")
paths = [path.strip() for path in raw_paths.split(";") if path.strip()]
summary = ingest_pdf_corpus_data(paths)

print(f"status: {summary.get('status', 'unknown')}")
if summary.get("message"):
    print(f"message: {summary['message']}")
if summary.get("chunk_count") is not None:
    print(f"chunks: {summary['chunk_count']}")
if summary.get("embedding_count") is not None:
    print(f"embeddings: {summary['embedding_count']}")
PY
