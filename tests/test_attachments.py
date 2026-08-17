import unittest

from pydantic import ValidationError

from schemas.api import AnalyzeRequest
from utils.attachments import (
    extract_urls,
    infer_attachment_type,
    is_youtube_video_url,
    normalize_attachments,
    validate_transcription_format,
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

    def test_recognizes_supported_youtube_video_urls(self) -> None:
        urls = (
            "https://www.youtube.com/watch?v=video-id",
            "https://youtu.be/video-id",
            "https://www.youtube.com/shorts/video-id",
            "https://www.youtube.com/live/video-id",
            "https://www.youtube-nocookie.com/embed/video-id",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(is_youtube_video_url(url))
                self.assertEqual(infer_attachment_type(url), "youtube")

    def test_rejects_non_video_and_lookalike_youtube_urls(self) -> None:
        urls = (
            "https://www.youtube.com/playlist?list=playlist-id",
            "https://www.youtube.com/watch",
            "https://youtube.com.example.org/watch?v=video-id",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(is_youtube_video_url(url))

    def test_normalizes_explicit_youtube_video_before_transcription_validation(
        self,
    ) -> None:
        attachments = normalize_attachments(None, [{
            "type": "video",
            "url": "https://www.youtube.com/watch?v=video-id",
        }])

        self.assertEqual(attachments[0]["type"], "youtube")

    def test_accepts_only_one_youtube_video_per_analysis(self) -> None:
        with self.assertRaisesRegex(ValueError, "no máximo um vídeo"):
            normalize_attachments(
                "Compare https://youtu.be/video-a com "
                "https://www.youtube.com/watch?v=video-b"
            )

    def test_accepts_supported_transcription_extensions(self) -> None:
        for extension in (
            ".mpeg", ".ogg", ".mp3", ".wav", ".mp4", ".avi", ".webm",
        ):
            with self.subTest(extension=extension):
                attachment_type = (
                    "audio" if extension in {".ogg", ".mp3", ".wav"}
                    else "video"
                )
                attachment = {
                    "type": attachment_type,
                    "url": f"https://example.com/file{extension}",
                }

                normalized = normalize_attachments(None, [attachment])

                self.assertEqual(len(normalized), 1)

    def test_accepts_supported_mime_when_url_has_no_extension(self) -> None:
        attachments = normalize_attachments(None, [{
            "type": "audio",
            "url": "https://example.com/download?token=123",
            "mime_type": "audio/ogg; codecs=opus",
        }])

        self.assertEqual(attachments[0]["type"], "audio")

    def test_rejects_unsupported_transcription_extension(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            r"Formato de mídia não suportado: \.m4a",
        ):
            normalize_attachments(None, [{
                "type": "audio",
                "url": "https://example.com/audio.m4a",
                "mime_type": "audio/mp4",
            }])

    def test_rejects_media_without_extension_or_supported_mime(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "Formato de mídia não suportado: não identificado",
        ):
            validate_transcription_format(AnalyzeRequest(attachments=[{
                "type": "audio",
                "url": "https://example.com/download",
            }]).attachments[0])

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
