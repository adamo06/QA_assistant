#!/bin/sh
set -eu

CHROMA_DB_DIR="${CHROMA_DB_DIR:-/app/chroma_db}"
PDF_CORPUS_PATHS_VALUE="${PDF_CORPUS_PATHS:-/app/data}"
CHROMA_SENTINEL="${CHROMA_DB_DIR}/chroma.sqlite3"

if [ ! -f "${CHROMA_SENTINEL}" ]; then
    echo "Index Chroma absent: ingestion du corpus depuis ${PDF_CORPUS_PATHS_VALUE}"
    PDF_CORPUS_PATHS="${PDF_CORPUS_PATHS_VALUE}" python - <<'PY'
import os
from tools.search import ingest_pdf_corpus_data

raw_paths = os.getenv("PDF_CORPUS_PATHS", "/app/data")
paths = [path.strip() for path in raw_paths.split(";") if path.strip()]
summary = ingest_pdf_corpus_data(paths)
print(summary.get("status", "unknown"))
print(summary.get("message", ""))
PY
fi

exec "$@"
