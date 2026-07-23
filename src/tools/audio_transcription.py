from time import monotonic, sleep

import json5
import requests
from langchain_core.tools import tool

from config import (
    TRANSCRIPTION_API_KEY,
    TRANSCRIPTION_POLL_INTERVAL_SECONDS,
    TRANSCRIPTION_REQUEST_TIMEOUT_SECONDS,
    TRANSCRIPTION_REQUEST_URL,
    TRANSCRIPTION_STATUS_URL,
    TRANSCRIPTION_TIMEOUT_SECONDS,
)

PROCESSING_STATUSES = {"IN_QUEUE", "IN_PROGRESS"}
FAILURE_STATUSES = {"FAILED", "CANCELLED", "TIMED_OUT"}


class TranscriptionError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not TRANSCRIPTION_API_KEY:
        raise TranscriptionError("A chave da API de transcrição não foi configurada.")

    return {
        "Authorization": f"Bearer {TRANSCRIPTION_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def submit_transcription(audio_url: str) -> str:
    """Envia uma URL pública de áudio e retorna o ID da transcrição.

    Raises:
        TranscriptionError: Se a configuração estiver ausente, a requisição
            falhar ou a API não retornar um identificador válido.
    """

    if not TRANSCRIPTION_REQUEST_URL:
        raise TranscriptionError("A URL de envio da transcrição não foi configurada.")

    payload = {
        "input": {
            "audio": audio_url,
            "word_timestamps": False,
        }
    }

    try:
        response = requests.post(
            TRANSCRIPTION_REQUEST_URL,
            json=payload,
            headers=_headers(),
            timeout=TRANSCRIPTION_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise TranscriptionError(
            "Não foi possível enviar o áudio para transcrição."
        ) from exc
    except ValueError as exc:
        raise TranscriptionError(
            "A API retornou uma resposta inválida ao solicitar a transcrição."
        ) from exc

    if not isinstance(data, dict):
        raise TranscriptionError(
            "A API retornou um formato inválido ao solicitar a transcrição."
        )

    transcription_id = data.get("id")
    if not transcription_id:
        raise TranscriptionError("A API não retornou o ID da transcrição.")

    return str(transcription_id)


def check_transcription_status(transcription_id: str) -> dict:
    if not TRANSCRIPTION_STATUS_URL:
        raise TranscriptionError("A URL de status da transcrição não foi configurada.")

    status_url = f"{TRANSCRIPTION_STATUS_URL.rstrip('/')}/{transcription_id}"

    try:
        response = requests.get(
            status_url,
            headers=_headers(),
            timeout=TRANSCRIPTION_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        raise TranscriptionError(
            "Não foi possível consultar o status da transcrição."
        ) from exc
    except ValueError as exc:
        raise TranscriptionError(
            "A API retornou uma resposta de status inválida."
        ) from exc

    if not isinstance(data, dict):
        raise TranscriptionError(
            "A API retornou um formato inválido ao consultar a transcrição."
        )

    return data


def wait_for_transcription(transcription_id: str) -> str:
    """Aguarda a conclusão da transcrição e retorna o texto produzido.

    Consulta periodicamente o status até receber ``COMPLETED`` ou atingir um
    estado de falha ou o limite de tempo configurado.

    Raises:
        TranscriptionError: Se a API falhar, retornar um estado inválido,
            concluir sem texto ou exceder o timeout.
    """

    started_at = monotonic()

    while monotonic() - started_at <= TRANSCRIPTION_TIMEOUT_SECONDS:
        data = check_transcription_status(transcription_id)
        status = str(data.get("status", "")).upper()

        if status == "COMPLETED":
            output = data.get("output") or {}
            if not isinstance(output, dict):
                raise TranscriptionError(
                    "A transcrição foi concluída, mas output possui formato inválido."
                )

            transcription = str(output.get("text", "")).strip()

            if not transcription:
                raise TranscriptionError(
                    "A transcrição foi concluída, mas output.text está vazio."
                )

            return transcription

        if status in FAILURE_STATUSES:
            details = data.get("error") or data.get("message") or status
            raise TranscriptionError(f"A transcrição terminou com falha: {details}.")

        if status not in PROCESSING_STATUSES:
            raise TranscriptionError(
                f"A API retornou um status de transcrição desconhecido: {status or 'vazio'}."
            )

        sleep(TRANSCRIPTION_POLL_INTERVAL_SECONDS)

    raise TranscriptionError(
        f"A transcrição excedeu o limite de {TRANSCRIPTION_TIMEOUT_SECONDS:g} segundos."
    )


@tool("audio_transcription")
def audio_transcription(file_path: str) -> str:
    """Transcreve o áudio de uma URL pública e retorna seu conteúdo textual."""

    try:
        transcription_id = submit_transcription(file_path)
        transcription = wait_for_transcription(transcription_id)
    except TranscriptionError as exc:
        return json5.dumps(
            {
                "url": file_path,
                "erro": str(exc),
            },
            ensure_ascii=False,
        )

    return json5.dumps(
        {
            "transcription_id": transcription_id,
            "results": transcription,
        },
        ensure_ascii=False,
    )
