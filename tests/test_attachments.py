import unittest

from pydantic import ValidationError

from schemas.api import AnalyzeRequest
from utils.attachments import (
    extract_urls,
    infer_attachment_type,
    normalize_attachments,
)


class AttachmentsTest(unittest.TestCase):
    def test_extracts_all_urls_from_query(self) -> None:
        urls = extract_urls(
            "Compare https://example.com/imagem.jpg com "
            "https://example.com/video.mp4."
        )

        self.assertEqual(urls, [
            "https://example.com/imagem.jpg",
            "https://example.com/video.mp4",
        ])

    def test_combines_payload_and_query_attachments_without_duplicates(self) -> None:
        attachments = normalize_attachments(
            "Compare https://example.com/imagem.jpg com "
            "https://example.com/noticia",
            [{
                "type": "image",
                "url": "https://example.com/imagem.jpg",
                "mime_type": "image/jpeg",
            }],
        )

        self.assertEqual(len(attachments), 2)
        self.assertEqual(attachments[0], {
            "type": "image",
            "url": "https://example.com/imagem.jpg",
            "mime_type": "image/jpeg",
            "origin": "payload",
        })
        self.assertEqual(attachments[1]["type"], "web")
        self.assertEqual(attachments[1]["origin"], "query")

    def test_infers_media_type_from_mime_type_and_url(self) -> None:
        self.assertEqual(
            infer_attachment_type("https://example.com/file", "audio/ogg"),
            "audio",
        )
        self.assertEqual(
            infer_attachment_type("https://example.com/file.webp"),
            "image",
        )
        self.assertEqual(
            infer_attachment_type("https://example.com/file.mp4?token=123"),
            "video",
        )

    def test_normalization_preserves_query_origin_when_repeated(self) -> None:
        first_pass = normalize_attachments(
            "Veja https://example.com/imagem.jpg"
        )
        second_pass = normalize_attachments(
            "Veja https://example.com/imagem.jpg",
            first_pass,
        )

        self.assertEqual(len(second_pass), 1)
        self.assertEqual(second_pass[0]["origin"], "query")

    def test_rejects_more_than_the_configured_limit(self) -> None:
        query = " ".join(
            f"https://example.com/{index}.jpg"
            for index in range(3)
        )

        with self.assertRaisesRegex(ValueError, "no máximo 2"):
            normalize_attachments(query, max_items=2)

    def test_request_requires_query_or_attachment(self) -> None:
        with self.assertRaises(ValidationError):
            AnalyzeRequest()

        request = AnalyzeRequest(attachments=[{
            "type": "audio",
            "url": "https://example.com/audio.ogg",
        }])

        self.assertIsNone(request.query)
        self.assertEqual(request.attachments[0].type, "audio")


if __name__ == "__main__":
    unittest.main()
