import os
import uuid
from functools import cache

from dotenv import load_dotenv
from fastembed import (
    LateInteractionTextEmbedding,
    SparseTextEmbedding,
    TextEmbedding,
)
from qdrant_client import QdrantClient, models

from graph.state import FinalAnswerResult

load_dotenv()

DENSE_MODEL = os.getenv(
    "DENSE_MODEL", "intfloat/multilingual-e5-large"
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
        port=os.getenv("QDRANT_API_PORT")
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


def save_final_answer(
    query: str,
    final_answer: FinalAnswerResult,
    point_id: str | None = None,
    collection_name: str = COLLECTION_NAME,
) -> str:
    document_text = (
        f"Pergunta: {query}\n\n"
        f"Resposta: {final_answer.answer}"
    )

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
            "text": f"passage: {document_text}",
            "meta": "verifica-ai",
            "query": query,
            "answer": final_answer.answer,
            "sources": [
                source.model_dump() for source in final_answer.sources
            ],
        },
    )

    qdrant = get_qdrant_client()
    ensure_collection(qdrant, collection_name)
    qdrant.upsert(
        collection_name=collection_name,
        points=[point],
        wait=True,
    )

    return point_id
