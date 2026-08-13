import unittest
from unittest.mock import patch

import json5

from integrations.gcs_media_relay import MediaRelayError


class AudioTranscriptionRelayTest(unittest.TestCase):
    @patch("tools.audio_transcription.TRANSCRIPTION_MEDIA_RELAY_ENABLED", False)
    @patch("tools.audio_transcription.wait_for_transcription", return_value="texto")
    @patch("tools.audio_transcription.submit_transcription", return_value="job-id")
    def test_uses_original_url_when_relay_is_disabled(
        self,
        submit_transcription,
        wait_for_transcription,
    ) -> None:
        from tools.audio_transcription import audio_transcription

        result = json5.loads(
            audio_transcription.func("https://internal/audio.ogg")
        )

        submit_transcription.assert_called_once_with("https://internal/audio.ogg")
        wait_for_transcription.assert_called_once_with("job-id")
        self.assertEqual(result["results"], "texto")

    @patch("tools.audio_transcription.TRANSCRIPTION_MEDIA_RELAY_ENABLED", True)
    @patch("tools.audio_transcription.temporary_transcription_url")
    def test_reports_relay_error_without_replacing_original_url(
        self,
        temporary_url,
    ) -> None:
        from tools.audio_transcription import audio_transcription

        temporary_url.return_value.__enter__.side_effect = MediaRelayError(
            "Falha segura no relay."
        )
        original_url = "https://internal/audio.ogg"

        result = json5.loads(audio_transcription.func(original_url))

        self.assertEqual(result["url"], original_url)
        self.assertEqual(result["erro"], "Falha segura no relay.")

    @patch("tools.audio_transcription.TRANSCRIPTION_MEDIA_RELAY_ENABLED", True)
    @patch("tools.audio_transcription.wait_for_transcription", return_value="texto")
    @patch("tools.audio_transcription.submit_transcription", return_value="job-id")
    @patch("tools.audio_transcription.temporary_transcription_url")
    def test_sends_only_signed_url_to_runpod_when_relay_is_enabled(
        self,
        temporary_url,
        submit_transcription,
        wait_for_transcription,
    ) -> None:
        from tools.audio_transcription import audio_transcription

        temporary_url.return_value.__enter__.return_value = (
            "https://storage.example/signed"
        )
        result = json5.loads(
            audio_transcription.func("https://internal/audio.ogg")
        )

        temporary_url.assert_called_once_with("https://internal/audio.ogg")
        submit_transcription.assert_called_once_with("https://storage.example/signed")
        wait_for_transcription.assert_called_once_with("job-id")
        self.assertEqual(result["results"], "texto")
