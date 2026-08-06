import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from graph.state import Attachment


URL_PATTERN = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"

IMAGE_EXTENSIONS = {
    ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png",
    ".tif", ".tiff", ".webp",
}
VIDEO_EXTENSIONS = {
    ".3gp", ".avi", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm",
}
AUDIO_EXTENSIONS = {
    ".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav",
}


def extract_urls(query: str | None) -> list[str]:
    """Return every HTTP(S) URL found in the original query."""
    if not query:
        return []

    return [
        match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        for match in URL_PATTERN.finditer(query)
    ]


def infer_attachment_type(url: str, mime_type: str | None = None) -> str:
    """Infer the attachment type from MIME type and URL path."""
    normalized_mime = (mime_type or "").split(";", 1)[0].strip().lower()
    if normalized_mime.startswith("image/"):
        return "image"
    if normalized_mime.startswith("video/"):
        return "video"
    if normalized_mime.startswith("audio/"):
        return "audio"
    if normalized_mime == "text/html":
        return "web"

    extension = PurePosixPath(urlsplit(url).path).suffix.lower()
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in VIDEO_EXTENSIONS:
        return "video"
    if extension in AUDIO_EXTENSIONS:
        return "audio"

    return "web"


def normalize_attachments(
    query: str | None,
    attachments: Iterable[Attachment | dict] = (),
    *,
    max_items: int = 10,
) -> list[dict]:
    """Merge explicit attachments with links found in the query."""
    normalized: list[Attachment] = []
    seen_urls: set[str] = set()

    for item in attachments:
        attachment = Attachment.model_validate(item)
        if attachment.type == "unknown":
            attachment.type = infer_attachment_type(
                str(attachment.url),
                attachment.mime_type,
            )

        url = str(attachment.url)
        if url in seen_urls:
            continue

        normalized.append(attachment)
        seen_urls.add(url)

    for url in extract_urls(query):
        attachment = Attachment(
            type=infer_attachment_type(url),
            url=url,
            origin="query",
        )
        normalized_url = str(attachment.url)
        if normalized_url in seen_urls:
            continue

        normalized.append(attachment)
        seen_urls.add(normalized_url)

    if len(normalized) > max_items:
        raise ValueError(
            f"A análise aceita no máximo {max_items} attachments."
        )

    return [attachment.model_dump(mode="json") for attachment in normalized]
