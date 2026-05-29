import os
from time import monotonic, sleep
from urllib.parse import urlparse

import json5
import requests
from langchain_core.tools import tool


def _extract_title_from_markdown(document: str) -> str:
    """Return the first markdown heading found in the document as its title."""
    for line in document.splitlines():
        cleaned_line = line.strip()
        if cleaned_line.startswith("#"):
            return cleaned_line.lstrip("#").strip()
    return ""


def _extract_excerpt_from_markdown(document: str, max_length: int = 400) -> str:
    """Build a plain-text excerpt from markdown content, limited to max_length."""
    lines = []
    for line in document.splitlines():
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
        if cleaned_line.startswith("#"):
            continue
        if cleaned_line.startswith("<!--") and cleaned_line.endswith("-->"):
            continue
        lines.append(cleaned_line)

    excerpt = " ".join(lines)
    if len(excerpt) <= max_length:
        return excerpt

    return excerpt[: max_length - 3].rstrip() + "..."


@tool("fetch_url")
def fetch_url(url: str) -> str:
    """Lê uma URL com o endpoint do Docling e retorna o conteúdo convertido para markdown.

    Use esta tool depois de `get_links` para abrir uma fonte específica e obter seu
    conteúdo principal em markdown limpo. A tool envia a URL para o endpoint do Docling,
    aguarda o processamento terminar e devolve o documento convertido junto dos metadados
    principais da execução.
    """

    base_url = os.getenv("DOCLING_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    bearer_token = os.getenv("DOCLING_BEARER_TOKEN")
    submit_url = os.getenv("DOCLING_SUBMIT_URL", f"{base_url}/document_to_markdown")
    status_url_template = os.getenv(
        "DOCLING_STATUS_URL_TEMPLATE", f"{base_url}/status/{{task_id}}"
    )
    timeout_seconds = float(os.getenv("DOCLING_TIMEOUT_SECONDS", "60"))
    poll_interval_seconds = float(os.getenv("DOCLING_POLL_INTERVAL_SECONDS", "1"))

    if not bearer_token:
        return json5.dumps(
            {
                "url": url,
                "erro": "A variável de ambiente DOCLING_BEARER_TOKEN não foi definida.",
            },
            ensure_ascii=False,
        )

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    }

    payload = {
        "url": url,
        "include_full_text": "true",
    }

    try:
        submit_response = requests.post(
            submit_url,
            data=payload,
            headers=headers,
            timeout=60,
        )
        submit_response.raise_for_status()
        submit_data = submit_response.json()
    except requests.exceptions.RequestException as e:
        return json5.dumps(
            {
                "url": url,
                "erro": "Não foi possível enviar a URL para o Docling.",
                "detalhes": str(e),
            },
            ensure_ascii=False,
        )
    except ValueError as e:
        return json5.dumps(
            {
                "url": url,
                "erro": "O endpoint do Docling retornou uma resposta inválida ao criar a tarefa.",
                "detalhes": str(e),
            },
            ensure_ascii=False,
        )

    task_id = submit_data.get("task_id")
    if not task_id:
        return json5.dumps(
            {
                "url": url,
                "erro": "O endpoint do Docling não retornou task_id.",
                "resposta": submit_data,
            },
            ensure_ascii=False,
        )

    started_at = monotonic()

    while monotonic() - started_at <= timeout_seconds:
        try:
            status_response = requests.get(
                status_url_template.format(task_id=task_id),
                headers=headers,
                timeout=30,
            )
            status_response.raise_for_status()
            status_data = status_response.json()
        except requests.exceptions.RequestException as e:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "erro": "Não foi possível consultar o status da tarefa no Docling.",
                    "detalhes": str(e),
                },
                ensure_ascii=False,
            )
        except ValueError as e:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "erro": "O endpoint de status do Docling retornou uma resposta inválida.",
                    "detalhes": str(e),
                },
                ensure_ascii=False,
            )

        status = status_data.get("status", "").lower()

        if status == "done":
            result = status_data.get("result", {})
            document = result.get("document", "")
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            title = _extract_title_from_markdown(document)
            excerpt = _extract_excerpt_from_markdown(document)

            return json5.dumps(
                {
                    "url": url,
                    "domain": domain,
                    "task_id": task_id,
                    "status": status_data.get("status"),
                    "elapsed_seconds": status_data.get("elapsed_seconds"),
                    "title": title,
                    "excerpt": excerpt,
                    "content_length": len(document),
                    "document": document,
                    "source_type": "docling",
                },
                ensure_ascii=False,
            )

        if status in {"error", "failed", "cancelled"}:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "status": status_data.get("status"),
                    "erro": "O Docling não conseguiu processar a URL.",
                    "detalhes": status_data,
                },
                ensure_ascii=False,
            )

        sleep(poll_interval_seconds)

    return json5.dumps(
        {
            "url": url,
            "task_id": task_id,
            "erro": "Timeout aguardando o processamento da URL no Docling.",
            "timeout_seconds": timeout_seconds,
        },
        ensure_ascii=False,
    )
