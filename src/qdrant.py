import logging
import os
import uuid
from datetime import datetime, timezone
from functools import cache
from typing import Any

from dotenv import load_dotenv
from fastembed import (
    LateInteractionTextEmbedding,
    SparseTextEmbedding,
    TextEmbedding,
)
from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import trace
from qdrant_client import QdrantClient, models
from rq import get_current_job

from graph.state import FinalAnswerResult
from queueing import qdrant_enabled
from utils.attachments import extract_url_keys, extract_urls, strip_urls
from utils.title_formatting import strip_classification_prefix

logger = logging.getLogger(__name__)

load_dotenv()
load_dotenv(".env.qdrant")

DENSE_MODEL = os.getenv(
    "QDRANT_DENSE_MODEL", "intfloat/multilingual-e5-large"
)
SPARSE_MODEL = os.getenv(
    "QDRANT_SPARSE_MODEL",
    "Qdrant/bm25",
)
COLBERT_MODEL = os.getenv(
    "QDRANT_COLBERT_MODEL",
    "colbert-ir/colbertv2.0",
)
MAX_TOKENS = int(os.getenv("QDRANT_MAX_TOKENS", "800"))
TIMEOUT_SECONDS = int(os.getenv("QDRANT_TIMEOUT_SECONDS", "60"))
COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION_NAME",
    "chatbot_cac",
)


@cache
def get_dense_model() -> TextEmbedding:
    return TextEmbedding(model_name=DENSE_MODEL)


@cache
def get_sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=SPARSE_MODEL)


@cache
def get_colbert_model() -> LateInteractionTextEmbedding:
    return LateInteractionTextEmbedding(model_name=COLBERT_MODEL)


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=os.getenv("QDRANT_API_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        port=os.getenv("QDRANT_API_PORT"),
        timeout=TIMEOUT_SECONDS,
    )


def ensure_collection(
    qdrant: QdrantClient,
    collection_name: str = COLLECTION_NAME,
) -> None:
    if qdrant.collection_exists(collection_name):
        return

    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(
                size=qdrant.get_embedding_size(DENSE_MODEL),
                distance=models.Distance.COSINE,
            ),
            "colbert": models.VectorParams(
                size=128,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM,
                ),
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(),
        },
    )
    qdrant.create_payload_index(
        collection_name=collection_name,
        field_name="url_keys",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )


def try_ensure_collection() -> bool:
    if not qdrant_enabled():
        return False

    try:
        ensure_collection(get_qdrant_client())
    except Exception:
        logger.warning(
            "Qdrant indisponivel; a aplicacao continuara sem persistencia.",
            exc_info=True,
        )
        return False

    return True


def store_qdrant_result_job(
    query: str,
    final_answer: dict,
    point_id: str | None = None,
) -> str | None:
    """Persist a validated result and flush its standalone LangSmith trace.

    Qdrant failures remain visible to RQ so its retry policy can run, while
    tracing and trace-flush failures are logged without changing the job result.
    """
    if not qdrant_enabled():
        return None

    job = get_current_job()
    started_at = datetime.now(timezone.utc)
    try:
        try:
            stored_point_id = save_final_answer(
                query=query,
                final_answer=FinalAnswerResult.model_validate(final_answer),
                point_id=point_id,
            )
        except Exception as exc:
            _trace_qdrant_store(
                point_id,
                job=job,
                started_at=started_at,
                stored=False,
                error=type(exc).__name__,
            )
            raise

        _trace_qdrant_store(
            point_id,
            job=job,
            started_at=started_at,
            stored=True,
            stored_point_id=stored_point_id,
        )
        return stored_point_id
    finally:
        if job is not None:
            try:
                wait_for_all_tracers()
            except Exception:
                logger.exception(
                    "Falha ao finalizar trace de persistencia no Qdrant."
                )


def _trace_qdrant_store(
    task_id: str | None,
    *,
    job: Any,
    started_at: datetime,
    stored: bool,
    stored_point_id: str | None = None,
    error: str | None = None,
) -> None:
    """Record sanitized Qdrant persistence metadata in an isolated trace."""
    try:
        with trace(
            "verificaai_qdrant_store",
            inputs={"task_id": task_id},
            tags=["flow:qdrant_store"],
            metadata={
                "task_id": task_id,
                "app_version": os.getenv("APP_VERSION", "0.0.1"),
                "rq_job_id": getattr(job, "id", None),
                "rq_retries_left": getattr(job, "retries_left", None),
                "collection": COLLECTION_NAME,
            },
            parent="ignore",
            start_time=started_at,
        ) as run:
            outputs = {"stored": stored}
            if stored_point_id is not None:
                outputs["point_id"] = stored_point_id

            run.end(outputs=outputs, error=error)
    except Exception:
        logger.exception("Falha ao registrar trace de persistencia no Qdrant.")


def save_final_answer(
    query: str,
    final_answer: FinalAnswerResult,
    point_id: str | None = None,
    collection_name: str = COLLECTION_NAME,
) -> str:
    qdrant = get_qdrant_client()
    ensure_collection(qdrant, collection_name)

    title = strip_classification_prefix(final_answer.title)
    document_text = build_qdrant_document_text(query, title)
    urls = extract_urls(query)
    url_keys = extract_url_keys(query)

    dense_embedding = next(get_dense_model().passage_embed([document_text]))
    sparse_embedding = next(get_sparse_model().passage_embed([document_text]))
    colbert_embedding = next(get_colbert_model().passage_embed([document_text]))

    point_id = point_id or str(uuid.uuid4())
    point = models.PointStruct(
        id=point_id,
        vector={
            "dense": dense_embedding.tolist(),
            "sparse": sparse_embedding.as_object(),
            "colbert": colbert_embedding.tolist(),
        },
        payload={
            "text": document_text,
            "meta": os.getenv("APP_NAME", "verifica-ai"),
            "query": query,
            "title": title,
            "urls": urls,
            "url_keys": url_keys,
        },
    )

    qdrant.upsert(
        collection_name=collection_name,
        points=[point],
        wait=True,
    )

    return point_id


def build_qdrant_document_text(query: str, title: str) -> str:
    """Build semantic text without embedding URLs from the original query."""
    document_parts = []
    semantic_query = strip_urls(query)
    if semantic_query:
        document_parts.append(f"Pergunta: {semantic_query}")
    if title:
        document_parts.append(f"Título: {title}")
    if not document_parts:
        document_parts.append(f"Pergunta: {query}")
    return "\n\n".join(document_parts)
