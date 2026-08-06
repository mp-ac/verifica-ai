import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
        )

        response = await analyze(payload, Mock())

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


if __name__ == "__main__":
    unittest.main()
