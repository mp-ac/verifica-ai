import os
from dotenv import load_dotenv
from functools import cache
from qdrant_client import QdrantClient, models

from fastembed import (
    TextEmbedding,
    SparseTextEmbedding,
    LateInteractionTextEmbedding
)

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
