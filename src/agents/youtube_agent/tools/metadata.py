from dataclasses import dataclass

import requests


YOUTUBE_OEMBED_URL = "https://www.youtube.com/oembed"
YOUTUBE_METADATA_TIMEOUT_SECONDS = 15


class YouTubeMetadataError(RuntimeError):
    """Raised when public YouTube metadata cannot be retrieved safely."""


@dataclass(frozen=True)
class YouTubeMetadata:
    title: str | None = None
    thumbnail_url: str | None = None


def get_youtube_metadata(video_url: str) -> YouTubeMetadata:
    """Return the official public title and thumbnail without an API key."""
    try:
        response = requests.get(
            YOUTUBE_OEMBED_URL,
            params={"url": video_url, "format": "json"},
            headers={"Accept": "application/json"},
            timeout=YOUTUBE_METADATA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise YouTubeMetadataError(
            "Não foi possível obter os metadados públicos do vídeo."
        ) from error

    if not isinstance(payload, dict):
        raise YouTubeMetadataError(
            "O YouTube retornou metadados em formato inválido."
        )

    title = str(payload.get("title") or "").strip() or None
    if title is None:
        raise YouTubeMetadataError(
            "O YouTube não informou o título público do vídeo."
        )

    thumbnail_url = str(payload.get("thumbnail_url") or "").strip() or None
    return YouTubeMetadata(title=title, thumbnail_url=thumbnail_url)
