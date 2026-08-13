"""Disponibiliza temporariamente mídias privadas por uma URL assinada do GCS."""

import hashlib
import logging
import mimetypes
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Iterator
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
from google.cloud import storage
from google.oauth2 import service_account

from config import (
    GCS_BUCKET_NAME,
    GCS_MEDIA_MAX_SIZE_MIB,
    GCS_OBJECT_PREFIX,
    GCS_SERVICE_ACCOUNT_FILE,
    GCS_SIGNED_URL_TTL_SECONDS,
    GOOGLE_CLOUD_PROJECT,
    TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS,
    TRANSCRIPTION_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS = (10, 60)
SPOOL_MAX_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5


class MediaRelayError(RuntimeError):
    """Indica uma falha ao preparar a mídia temporária para a transcrição."""


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        raise MediaRelayError("A mídia para transcrição precisa usar HTTPS.")
    if hostname not in TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS:
        raise MediaRelayError("O host da mídia não está autorizado para o relay.")


def _object_suffix(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and len(suffix) <= 10:
        return suffix
    return mimetypes.guess_extension(content_type) or ""


def _download_media(
    url: str,
) -> tuple[SpooledTemporaryFile, str, int, str]:
    _validate_source_url(url)
    max_size_bytes = GCS_MEDIA_MAX_SIZE_MIB * 1024 * 1024
    temporary_file = SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE_BYTES)
    digest = hashlib.sha256()
    downloaded_bytes = 0

    try:
        current_url = url
        response = None
        for _redirect_count in range(MAX_REDIRECTS + 1):
            _validate_source_url(current_url)
            response = requests.get(
                current_url,
                stream=True,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            if response.status_code not in REDIRECT_STATUS_CODES:
                break

            location = response.headers.get("Location")
            response.close()
            if not location:
                raise MediaRelayError(
                    "A origem retornou um redirecionamento inválido."
                )
            current_url = urljoin(current_url, location)
        else:
            raise MediaRelayError("A mídia excedeu o limite de redirecionamentos.")

        if response is None:
            raise MediaRelayError("A origem não retornou a mídia solicitada.")

        with response:
            response.raise_for_status()
            _validate_source_url(response.url)
            content_type = response.headers.get(
                "Content-Type",
                "application/octet-stream",
            ).split(";", 1)[0].strip().lower()
            if not content_type.startswith(ALLOWED_MEDIA_PREFIXES):
                raise MediaRelayError(
                    "A URL não retornou um áudio ou vídeo suportado."
                )

            declared_size = response.headers.get("Content-Length")
            if declared_size:
                try:
                    if int(declared_size) > max_size_bytes:
                        raise MediaRelayError(
                            "A mídia excede o tamanho máximo configurado."
                        )
                except ValueError as exc:
                    raise MediaRelayError(
                        "A origem retornou um tamanho de mídia inválido."
                    ) from exc

            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                downloaded_bytes += len(chunk)
                if downloaded_bytes > max_size_bytes:
                    raise MediaRelayError(
                        "A mídia excede o tamanho máximo configurado."
                    )
                digest.update(chunk)
                temporary_file.write(chunk)

        temporary_file.seek(0)
        return temporary_file, content_type, downloaded_bytes, digest.hexdigest()
    except MediaRelayError:
        temporary_file.close()
        raise
    except requests.exceptions.RequestException as exc:
        temporary_file.close()
        raise MediaRelayError(
            "Não foi possível baixar a mídia para o relay."
        ) from exc
    except Exception:
        temporary_file.close()
        raise


def _storage_client() -> storage.Client:
    if GCS_SERVICE_ACCOUNT_FILE:
        credentials = service_account.Credentials.from_service_account_file(
            GCS_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
        )
        return storage.Client(
            project=GOOGLE_CLOUD_PROJECT or credentials.project_id,
            credentials=credentials,
        )
    return storage.Client(project=GOOGLE_CLOUD_PROJECT)


def _upload_media(
    *,
    source_url: str,
    file_object: SpooledTemporaryFile,
    content_type: str,
    size: int,
    sha256: str,
) -> storage.Blob:
    if not GCS_BUCKET_NAME:
        raise MediaRelayError("O bucket do relay de mídia não foi configurado.")

    clean_prefix = GCS_OBJECT_PREFIX.strip("/")
    filename = f"{uuid4().hex}{_object_suffix(source_url, content_type)}"
    object_name = f"{clean_prefix}/{filename}" if clean_prefix else filename
    blob = _storage_client().bucket(GCS_BUCKET_NAME).blob(object_name)
    blob.cache_control = "private, no-store"
    blob.metadata = {"sha256": sha256}
    blob.upload_from_file(
        file_object,
        size=size,
        content_type=content_type,
        if_generation_match=0,
        checksum="auto",
    )
    return blob


@contextmanager
def temporary_transcription_url(source_url: str) -> Iterator[str]:
    """Cria uma URL assinada temporária e remove o objeto ao terminar."""
    if not TRANSCRIPTION_MEDIA_RELAY_ALLOWED_HOSTS:
        raise MediaRelayError("Nenhum host foi autorizado para o relay de mídia.")
    if GCS_MEDIA_MAX_SIZE_MIB <= 0:
        raise MediaRelayError("O tamanho máximo do relay deve ser maior que zero.")
    if GCS_SIGNED_URL_TTL_SECONDS <= TRANSCRIPTION_TIMEOUT_SECONDS:
        raise MediaRelayError(
            "A validade da URL assinada deve superar o timeout da transcrição."
        )

    media, content_type, size, sha256 = _download_media(source_url)
    blob = None
    try:
        try:
            blob = _upload_media(
                source_url=source_url,
                file_object=media,
                content_type=content_type,
                size=size,
                sha256=sha256,
            )
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=GCS_SIGNED_URL_TTL_SECONDS),
                method="GET",
            )
        except MediaRelayError:
            raise
        except Exception as exc:
            raise MediaRelayError(
                "Não foi possível disponibilizar a mídia para transcrição."
            ) from exc

        yield signed_url
    finally:
        media.close()
        if blob is not None:
            try:
                blob.delete(if_generation_match=blob.generation)
            except Exception:
                logger.exception(
                    "Falha ao remover objeto temporario do relay: object=%s",
                    blob.name,
                )
