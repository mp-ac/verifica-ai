import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from schemas.api import AnalyzeRequest


class AnalyzeAttachmentsTest(unittest.IsolatedAsyncioTestCase):
    @patch("main.q")
    async def test_enqueues_explicit_and_query_attachments(
        self,
        queue: Mock,
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


if __name__ == "__main__":
    unittest.main()
