import os
import unittest
from unittest.mock import Mock, patch

from similarity.client import (
    SemanticRetrieverError,
    retrieve_candidates,
    semantic_retriever_collection_name,
)


class SimilarityClientTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "SEMANTIC_RETRIEVER_COLLECTION_NAME": "",
            "QDRANT_COLLECTION_NAME": "stored-analyses",
        },
    )
    def test_collection_falls_back_to_qdrant_configuration(self) -> None:
        self.assertEqual(
            semantic_retriever_collection_name(),
            "stored-analyses",
        )

    @patch.dict(
        os.environ,
        {
            "SEMANTIC_RETRIEVER_API_URL": "https://retriever.test/semantic_retriever",
            "SEMANTIC_RETRIEVER_QDRANT_API_KEY": "qdrant-token",
            "SEMANTIC_RETRIEVER_COLLECTION_NAME": "analyses",
            "SEMANTIC_RETRIEVER_TIMEOUT_SECONDS": "7",
        },
    )
    @patch("similarity.client.requests.post")
    def test_sends_form_data_and_validates_candidates(self, post: Mock) -> None:
        response = post.return_value
        response.json.return_value = {
            "result": [{
                "id": "candidate-1",
                "match_type": "semantic",
                "rank": 1,
                "score": 12.5,
                "text": "Pergunta e título genéricos",
            }]
        }

        candidates = retrieve_candidates("Consulta genérica")

        post.assert_called_once_with(
            "https://retriever.test/semantic_retriever",
            data={
                "query": "Consulta genérica",
                "qdrant_collection_name": "analyses",
            },
            headers={
                "api-key": "qdrant-token",
                "Accept": "application/json",
            },
            timeout=7.0,
        )
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(candidates[0].id, "candidate-1")

    @patch.dict(
        os.environ,
        {
            "SEMANTIC_RETRIEVER_API_URL": "https://retriever.test/semantic_retriever",
            "SEMANTIC_RETRIEVER_QDRANT_API_KEY": "qdrant-token",
            "SEMANTIC_RETRIEVER_COLLECTION_NAME": "analyses",
        },
    )
    @patch("similarity.client.requests.post")
    def test_rejects_invalid_response(self, post: Mock) -> None:
        post.return_value.json.return_value = {
            "result": [{
                "id": "candidate-1",
                "match_type": "semantic",
                "rank": 1,
                "score": None,
                "text": "Candidato genérico",
            }]
        }

        with self.assertRaisesRegex(
            SemanticRetrieverError,
            "não devolveu uma resposta válida",
        ):
            retrieve_candidates("Consulta genérica")

    @patch.dict(os.environ, {}, clear=True)
    def test_requires_endpoint_token_and_collection(self) -> None:
        with self.assertRaisesRegex(
            SemanticRetrieverError,
            "API_URL",
        ):
            retrieve_candidates("Consulta genérica")
