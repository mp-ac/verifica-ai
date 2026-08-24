import re
from collections.abc import Iterable
from pathlib import PurePosixPath
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

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
TRACKING_QUERY_PARAMETERS = {
    "dclid",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


def extract_urls(query: str | None) -> list[str]:
    """Return every HTTP(S) URL found in the original query."""
    if not query:
        return []

    return [
        match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        for match in URL_PATTERN.finditer(query)
    ]


def strip_urls(value: str) -> str:
    """Remove HTTP(S) URLs and normalize the remaining whitespace."""
    return " ".join(URL_PATTERN.sub(" ", value).split())


def youtube_video_id(url: str) -> str | None:
    """Return the stable video ID from one supported YouTube URL."""
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in YOUTUBE_HOSTS:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if host in {"youtu.be", "www.youtu.be"}:
        return path_parts[0] if path_parts else None

    if parsed.path == "/watch":
        return parse_qs(parsed.query).get("v", [""])[0].strip() or None

    if len(path_parts) >= 2 and path_parts[0] in {
        "embed",
        "live",
        "shorts",
    }:
        return path_parts[1]

    return None


def canonical_url_key(url: str) -> str | None:
    """Return a stable key for exact URL matching without tracking data."""
    video_id = youtube_video_id(url)
    if video_id is not None:
        return f"youtube:{video_id}"

    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host:
        return None

    try:
        port = parsed.port
    except ValueError:
        return None

    if port is not None and not (
        (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"

    path = parsed.path.rstrip("/") or "/"
    query_items = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_QUERY_PARAMETERS
    )
    normalized_query = urlencode(query_items, doseq=True)
    suffix = f"?{normalized_query}" if normalized_query else ""
    return f"url:{host}{path}{suffix}"


def extract_url_keys(query: str | None) -> list[str]:
    """Return unique canonical keys for the URLs found in a query."""
    keys: list[str] = []
    for url in extract_urls(query):
        key = canonical_url_key(url)
        if key is not None and key not in keys:
            keys.append(key)
    return keys


def is_youtube_video_url(url: str) -> bool:
    """Return whether a URL identifies one supported YouTube video."""
    return youtube_video_id(url) is not None


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
