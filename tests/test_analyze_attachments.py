import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi import HTTPException

from schemas.api import AnalyzeRequest


class AnalyzeAttachmentsTest(unittest.IsolatedAsyncioTestCase):
    @patch("main.record_accepted_analyze_request")
    @patch("main.q")
    async def test_enqueues_explicit_and_query_attachments(
        self,
        queue: Mock,
        record_accepted: Mock,
    ) -> None:
        from main import analyze

        queue.enqueue.return_value = SimpleNamespace(id="task-id")
        payload = AnalyzeRequest(
            query=(
                "Compare https://example.com/imagem.jpg com o áudio enviado"
            ),
            attachments=[{
                "type": "audio",
                "url": "https://example.com/audio.ogg",
                "mime_type": "audio/ogg",
                "origin": "query",
            }],
            requester={
                "external_id": "+5568999999999",
                "conversation_id": "conversation-id",
                "message_id": "message-id",
            },
        )

        application_id = UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04")
        token_data = SimpleNamespace(
            application_id=application_id,
            name="Agente WhatsApp",
        )
        response = await analyze(payload, token_data)

        self.assertEqual(response.task_id, "task-id")
        enqueue_args = queue.enqueue.call_args.args
        self.assertEqual(enqueue_args[1], payload.query)
        self.assertEqual(enqueue_args[2], [
            {
                "type": "audio",
                "url": "https://example.com/audio.ogg",
                "mime_type": "audio/ogg",
                "origin": "payload",
            },
            {
                "type": "image",
                "url": "https://example.com/imagem.jpg",
                "mime_type": None,
                "origin": "query",
            },
        ])
        self.assertEqual(enqueue_args[3], {
            "application": {
                "id": str(application_id),
                "name": "Agente WhatsApp",
            },
            "external_id": "+5568999999999",
            "conversation_id": "conversation-id",
            "message_id": "message-id",
        })
        record_accepted.assert_called_once_with(
            task_id="task-id",
            application_id=application_id,
            application_name="Agente WhatsApp",
        )

    @patch("main.record_accepted_analyze_request")
    @patch("main.q")
    async def test_rejects_unsupported_media_before_enqueue(
        self,
        queue: Mock,
        record_accepted: Mock,
    ) -> None:
        from main import analyze

        payload = AnalyzeRequest(attachments=[{
            "type": "audio",
            "url": "https://example.com/audio.m4a",
            "mime_type": "audio/mp4",
        }])
        token_data = SimpleNamespace(
            application_id=UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04"),
            name="Agente WhatsApp",
        )

        with self.assertRaises(HTTPException) as context:
            await analyze(payload, token_data)

        self.assertEqual(context.exception.status_code, 422)
        self.assertIn(
            "Formato de mídia não suportado: .m4a",
            context.exception.detail,
        )
        queue.enqueue.assert_not_called()
        record_accepted.assert_not_called()

    @patch(
        "main.record_accepted_analyze_request",
        side_effect=RuntimeError("database unavailable"),
    )
    @patch("main.q")
    async def test_observability_failure_does_not_reject_accepted_request(
        self,
        queue: Mock,
        _record_accepted: Mock,
    ) -> None:
        from main import analyze

        queue.enqueue.return_value = SimpleNamespace(id="task-id")
        payload = AnalyzeRequest(query="Consulta")
        token_data = SimpleNamespace(
            application_id=UUID("c824bf11-2a72-43dd-919b-a3f76de5fe04"),
            name="Agente WhatsApp",
        )

        with self.assertLogs("main", level="ERROR"):
            response = await analyze(payload, token_data)

        self.assertEqual(response.task_id, "task-id")
        self.assertEqual(response.status, "queued")


if __name__ == "__main__":
    unittest.main()
