import unittest
from unittest.mock import Mock, patch


class GcsMediaRelayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.allowed_hosts = patch(
            "integrations.gcs_media_relay."
            "TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS",
            {"nat-bot.mpac.mp.br"},
        )
        self.max_size = patch(
            "integrations.gcs_media_relay.GCS_MEDIA_MAX_SIZE_MIB",
            250,
        )
        self.signed_url_ttl = patch(
            "integrations.gcs_media_relay.GCS_SIGNED_URL_TTL_SECONDS",
            900,
        )
        self.transcription_timeout = patch(
            "integrations.gcs_media_relay.TRANSCRIPTION_TIMEOUT_SECONDS",
            480,
        )
        for config_patch in (
            self.allowed_hosts,
            self.max_size,
            self.signed_url_ttl,
            self.transcription_timeout,
        ):
            config_patch.start()
            self.addCleanup(config_patch.stop)

    @patch("integrations.gcs_media_relay._storage_client")
    @patch("integrations.gcs_media_relay.GCS_BUCKET_NAME", "test-bucket")
    @patch("integrations.gcs_media_relay.requests.get")
    def test_generates_signed_url_and_removes_temporary_object(
        self,
        get: Mock,
        storage_client: Mock,
    ) -> None:
        from integrations.gcs_media_relay import temporary_transcription_url

        response = Mock()
        response.status_code = 200
        response.url = "https://nat-bot.mpac.mp.br/api/media/audio.ogg"
        response.headers = {
            "Content-Type": "audio/ogg",
            "Content-Length": "5",
        }
        response.iter_content.return_value = [b"audio"]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        get.return_value = response

        blob = storage_client.return_value.bucket.return_value.blob.return_value
        blob.generation = 7
        blob.name = "transcription-media/object.ogg"
        blob.generate_signed_url.return_value = "https://storage.example/signed"

        with temporary_transcription_url(response.url) as signed_url:
            self.assertEqual(signed_url, "https://storage.example/signed")

        blob.upload_from_file.assert_called_once()
        blob.generate_signed_url.assert_called_once()
        blob.delete.assert_called_once_with(if_generation_match=7)

    def test_rejects_non_allowed_source_host(self) -> None:
        from integrations.gcs_media_relay import (
            MediaRelayError,
            temporary_transcription_url,
        )

        with self.assertRaisesRegex(MediaRelayError, "não está autorizado"):
            with temporary_transcription_url("https://example.com/audio.ogg"):
                pass

    @patch("integrations.gcs_media_relay.GCS_SIGNED_URL_TTL_SECONDS", 480)
    def test_rejects_signed_url_ttl_that_can_expire_during_transcription(
        self,
    ) -> None:
        from integrations.gcs_media_relay import (
            MediaRelayError,
            temporary_transcription_url,
        )

        with self.assertRaisesRegex(MediaRelayError, "superar o timeout"):
            with temporary_transcription_url(
                "https://nat-bot.mpac.mp.br/api/media/audio.ogg"
            ):
                pass

    @patch("integrations.gcs_media_relay._storage_client")
    @patch("integrations.gcs_media_relay.GCS_BUCKET_NAME", "test-bucket")
    @patch("integrations.gcs_media_relay.requests.get")
    def test_rejects_non_media_content_type(
        self,
        get: Mock,
        storage_client: Mock,
    ) -> None:
        from integrations.gcs_media_relay import (
            MediaRelayError,
            temporary_transcription_url,
        )

        response = Mock()
        response.status_code = 200
        response.url = "https://nat-bot.mpac.mp.br/api/media/audio.ogg"
        response.headers = {"Content-Type": "text/html"}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        get.return_value = response

        with self.assertRaisesRegex(MediaRelayError, "áudio ou vídeo"):
            with temporary_transcription_url(response.url):
                pass

        storage_client.assert_not_called()

    @patch("integrations.gcs_media_relay.requests.get")
    def test_rejects_redirect_to_non_allowed_host(self, get: Mock) -> None:
        from integrations.gcs_media_relay import (
            MediaRelayError,
            temporary_transcription_url,
        )

        response = Mock()
        response.status_code = 302
        response.headers = {"Location": "https://example.com/audio.ogg"}
        get.return_value = response

        with self.assertRaisesRegex(MediaRelayError, "não está autorizado"):
            with temporary_transcription_url(
                "https://nat-bot.mpac.mp.br/api/media/audio.ogg"
            ):
                pass

        response.close.assert_called_once()

    @patch("integrations.gcs_media_relay._storage_client")
    @patch("integrations.gcs_media_relay.GCS_BUCKET_NAME", "test-bucket")
    @patch("integrations.gcs_media_relay.requests.get")
    def test_removes_object_when_transcription_fails(
        self,
        get: Mock,
        storage_client: Mock,
    ) -> None:
        from integrations.gcs_media_relay import temporary_transcription_url

        response = Mock()
        response.status_code = 200
        response.url = "https://nat-bot.mpac.mp.br/api/media/audio.ogg"
        response.headers = {"Content-Type": "audio/ogg"}
        response.iter_content.return_value = [b"audio"]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        get.return_value = response

        blob = storage_client.return_value.bucket.return_value.blob.return_value
        blob.generation = 8
        blob.name = "transcription-media/object.ogg"
        blob.generate_signed_url.return_value = "https://storage.example/signed"

        with self.assertRaisesRegex(RuntimeError, "Runpod falhou"):
            with temporary_transcription_url(response.url):
                raise RuntimeError("Runpod falhou")

        blob.delete.assert_called_once_with(if_generation_match=8)
