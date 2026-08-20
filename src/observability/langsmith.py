import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from langsmith import Client, tracing_context
from langsmith.utils import tracing_is_enabled


logger = logging.getLogger(__name__)

_SIGNATURE_KEYS = {"signature", "thoughtsignature"}


def remove_model_signatures(value: Any) -> Any:
    """Return trace data without opaque model reasoning signatures."""
    if isinstance(value, dict):
        return {
            key: remove_model_signatures(item)
            for key, item in value.items()
            if not (
                isinstance(key, str)
                and key.casefold().replace("_", "") in _SIGNATURE_KEYS
            )
        }

    if isinstance(value, list):
        return [remove_model_signatures(item) for item in value]

    return value


@lru_cache(maxsize=1)
def _sanitized_client() -> Client:
    return Client(anonymizer=remove_model_signatures)


@contextmanager
def sanitized_langsmith_tracing() -> Iterator[None]:
    """Use a LangSmith client that removes signatures before transmission."""
    if not tracing_is_enabled():
        yield
        return

    client = _sanitized_client()
    try:
        with tracing_context(client=client):
            yield
    finally:
        try:
            client.flush()
        except Exception:
            logger.exception("Falha ao finalizar traces sanitizados do LangSmith.")
