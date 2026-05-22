from pathlib import Path
import os


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = "openai:gpt-5.4-mini"
TEMPERATURE = 0
TIMEOUT = 300
MAX_TOKENS = 25000
THREAD_ID = "great-gatsby-da"
BUSINESS_API_BASE_URL = os.getenv("BUSINESS_API_BASE_URL", "http://127.0.0.1:8000")

SYSTEM_PROMPT = """You are a business document assistant.

## Capabilities

- `ingest_pdf_corpus`: loads and parses internal PDF documents into the corpus store.
- `retrieve_context`: retrieves relevant context from the vector store.
- `query_business_api`: queries the business API for operational document search and summary data.
Do not guess ingestion counts or corpus size-ground them in tool results from the parsed files."""
