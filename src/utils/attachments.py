import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlsplit

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
ALLOWED_TRANSCRIPTION_EXTENSIONS = {
    ".avi", ".mp3", ".mp4", ".mpeg", ".ogg", ".wav", ".webm",
}
ALLOWED_TRANSCRIPTION_MIME_TYPES = {
    "application/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/wave",
    "audio/webm",
    "audio/x-wav",
    "audio/vnd.wave",
    "video/avi",
    "video/mp4",
    "video/mpeg",
    "video/ogg",
    "video/webm",
    "video/x-msvideo",
}
ALLOWED_TRANSCRIPTION_FORMATS_LABEL = (
    ".mpeg, .ogg, .mp3, .wav, .mp4, .avi e .webm"
)
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
MAX_YOUTUBE_ATTACHMENTS = 1


def extract_urls(query: str | None) -> list[str]:
    """Return every HTTP(S) URL found in the original query."""
    if not query:
        return []

    return [
        match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        for match in URL_PATTERN.finditer(query)
    ]


def is_youtube_video_url(url: str) -> bool:
    """Return whether a URL identifies one supported YouTube video."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in YOUTUBE_HOSTS:
        return False

    path_parts = [part for part in parsed.path.split("/") if part]
    if host in {"youtu.be", "www.youtu.be"}:
        return bool(path_parts)

    if parsed.path == "/watch":
        return bool(parse_qs(parsed.query).get("v", [""])[0].strip())

    return (
        len(path_parts) >= 2
        and path_parts[0] in {"embed", "live", "shorts"}
    )


def infer_attachment_type(url: str, mime_type: str | None = None) -> str:
    """Infer the attachment type from MIME type and URL path."""
    if is_youtube_video_url(url):
        return "youtube"

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


def validate_transcription_format(attachment: Attachment) -> None:
    """Reject unsupported audio and video before they reach the queue."""
    if attachment.type not in {"audio", "video"}:
        return

    extension = PurePosixPath(urlsplit(str(attachment.url)).path).suffix.lower()
    normalized_mime = (
        (attachment.mime_type or "").split(";", 1)[0].strip().lower()
    )

    if extension:
        if extension in ALLOWED_TRANSCRIPTION_EXTENSIONS:
            return
        received_format = extension
    elif normalized_mime in ALLOWED_TRANSCRIPTION_MIME_TYPES:
        return
    else:
        received_format = normalized_mime or "não identificado"

    raise ValueError(
        f"Formato de mídia não suportado: {received_format}. "
        f"Formatos aceitos: {ALLOWED_TRANSCRIPTION_FORMATS_LABEL}."
    )


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
        if is_youtube_video_url(str(attachment.url)):
            attachment.type = "youtube"
        elif attachment.type == "unknown":
            attachment.type = infer_attachment_type(
                str(attachment.url),
                attachment.mime_type,
            )
        validate_transcription_format(attachment)

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
        validate_transcription_format(attachment)
        normalized_url = str(attachment.url)
        if normalized_url in seen_urls:
            continue

        normalized.append(attachment)
        seen_urls.add(normalized_url)

    if len(normalized) > max_items:
        raise ValueError(
            f"A análise aceita no máximo {max_items} attachments."
        )

    youtube_count = sum(
        attachment.type == "youtube"
        for attachment in normalized
    )
    if youtube_count > MAX_YOUTUBE_ATTACHMENTS:
        raise ValueError(
            "A análise aceita no máximo um vídeo do YouTube."
        )

    return [attachment.model_dump(mode="json") for attachment in normalized]
