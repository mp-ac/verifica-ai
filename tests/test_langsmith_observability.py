import unittest
from unittest.mock import Mock, patch

from observability.langsmith import (
    _sanitized_client,
    remove_model_signatures,
    sanitized_langsmith_tracing,
)


class LangSmithObservabilityTest(unittest.TestCase):
    def tearDown(self) -> None:
        _sanitized_client.cache_clear()

    def test_removes_nested_model_signatures_without_mutating_source(self) -> None:
        source = {
            "content": [
                {
                    "text": "Resposta",
                    "extras": {
                        "signature": "opaque-signature",
                        "provider": "google",
                    },
                },
                {"thought_signature": "opaque-thought-signature"},
                {"thoughtSignature": "opaque-camel-case-signature"},
            ],
            "metadata": {"model": "gemini"},
        }

        sanitized = remove_model_signatures(source)

        self.assertEqual(
            sanitized,
            {
                "content": [
                    {
                        "text": "Resposta",
                        "extras": {"provider": "google"},
                    },
                    {},
                    {},
                ],
                "metadata": {"model": "gemini"},
            },
        )
        self.assertEqual(
            source["content"][0]["extras"]["signature"],
            "opaque-signature",
        )

    @patch("observability.langsmith.Client")
    def test_configures_client_with_signature_anonymizer(
        self,
        client_class: Mock,
    ) -> None:
        client = _sanitized_client()

        self.assertIs(client, client_class.return_value)
        client_class.assert_called_once_with(anonymizer=remove_model_signatures)

    @patch("observability.langsmith.tracing_context")
    @patch("observability.langsmith._sanitized_client")
    @patch("observability.langsmith.tracing_is_enabled", return_value=True)
    def test_uses_sanitized_client_when_tracing_is_enabled(
        self,
        _tracing_enabled: Mock,
        sanitized_client: Mock,
        tracing_context: Mock,
    ) -> None:
        client = Mock()
        sanitized_client.return_value = client

        with sanitized_langsmith_tracing():
            pass

        tracing_context.assert_called_once_with(client=client)

    @patch("observability.langsmith.tracing_context")
    @patch("observability.langsmith._sanitized_client")
    @patch("observability.langsmith.tracing_is_enabled", return_value=False)
    def test_does_not_create_client_when_tracing_is_disabled(
        self,
        _tracing_enabled: Mock,
        sanitized_client: Mock,
        tracing_context: Mock,
    ) -> None:
        with sanitized_langsmith_tracing():
            pass

        sanitized_client.assert_not_called()
        tracing_context.assert_not_called()


if __name__ == "__main__":
    unittest.main()
