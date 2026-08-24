import os

import requests
from pydantic import BaseModel, Field, ValidationError

from similarity.schemas import RetrievedCandidate


class SemanticRetrieverResponse(BaseModel):
    """Validated response contract from the semantic retriever API."""

    result: list[RetrievedCandidate] = Field(max_length=3)


class SemanticRetrieverError(RuntimeError):
    """Raised when semantic retrieval cannot return a valid response."""


def semantic_retriever_enabled() -> bool:
    """Return whether duplicate retrieval is enabled for analyses."""
    return (
        os.getenv("SEMANTIC_RETRIEVER_ENABLED", "false").strip().lower()
        == "true"
    )


def semantic_retriever_api_url() -> str:
    """Return the configured semantic retriever endpoint."""
    return os.getenv("SEMANTIC_RETRIEVER_API_URL", "").strip()


def semantic_retriever_qdrant_api_key() -> str:
    """Return the Qdrant token forwarded in the API key header."""
    return os.getenv("SEMANTIC_RETRIEVER_QDRANT_API_KEY", "").strip()


def semantic_retriever_collection_name() -> str:
    """Return the Qdrant collection queried for previous analyses."""
    configured_name = os.getenv(
        "SEMANTIC_RETRIEVER_COLLECTION_NAME",
        "",
    ).strip()
    return configured_name or os.getenv("QDRANT_COLLECTION_NAME", "").strip()


def semantic_retriever_timeout_seconds() -> float:
    """Return the HTTP timeout for semantic retrieval."""
    return float(os.getenv("SEMANTIC_RETRIEVER_TIMEOUT_SECONDS", "10"))


def retrieve_candidates(query: str) -> list[RetrievedCandidate]:
    """Retrieve and validate up to three candidates for one query."""
    api_url = semantic_retriever_api_url()
    api_key = semantic_retriever_qdrant_api_key()
    collection_name = semantic_retriever_collection_name()
    if not api_url:
        raise SemanticRetrieverError(
            "SEMANTIC_RETRIEVER_API_URL não foi configurada."
        )
    if not api_key:
        raise SemanticRetrieverError(
            "SEMANTIC_RETRIEVER_QDRANT_API_KEY não foi configurada."
        )
    if not collection_name:
        raise SemanticRetrieverError(
            "SEMANTIC_RETRIEVER_COLLECTION_NAME não foi configurada."
        )

    try:
        response = requests.post(
            api_url,
            data={
                "query": query,
                "qdrant_collection_name": collection_name,
            },
            headers={
                "api-key": api_key,
                "Accept": "application/json",
            },
            timeout=semantic_retriever_timeout_seconds(),
        )
        response.raise_for_status()
        return SemanticRetrieverResponse.model_validate(
            response.json()
        ).result
    except (requests.RequestException, ValueError, ValidationError) as exc:
        raise SemanticRetrieverError(
            "O semantic retriever não devolveu uma resposta válida."
        ) from exc
