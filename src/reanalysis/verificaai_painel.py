from uuid import UUID

import requests
from pydantic import ValidationError

from final_results import (
    final_results_api_timeout_seconds,
    final_results_api_token,
    final_results_api_url,
)
from reanalysis.schemas import PanelFinalResult, PanelFinalResultResponse


class PanelApiError(RuntimeError):
    """Raised when the panel cannot provide a valid final result."""


class PanelFinalResultNotFoundError(PanelApiError):
    """Raised when the requested final result does not exist."""


class FinalResultAlreadyReviewedError(PanelApiError):
    """Raised when a human review makes the result ineligible."""


def fetch_final_result(final_result_id: UUID) -> PanelFinalResult:
    api_url = final_results_api_url()
    api_token = final_results_api_token()

    if not api_url:
        raise PanelApiError("FINAL_RESULTS_API_URL nao foi configurada.")
    if not api_token:
        raise PanelApiError("FINAL_RESULTS_API_TOKEN nao foi configurado.")

    try:
        response = requests.get(
            f"{api_url.rstrip('/')}/{final_result_id}",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json",
            },
            timeout=final_results_api_timeout_seconds(),
        )
    except requests.RequestException as exc:
        raise PanelApiError(
            "Não foi possível consultar o resultado original no painel."
        ) from exc

    if response.status_code == 404:
        raise PanelFinalResultNotFoundError(
            "Resultado final original não encontrado."
        )

    try:
        response.raise_for_status()
        final_result = PanelFinalResultResponse.model_validate(
            response.json()
        ).data
    except (requests.RequestException, ValueError, ValidationError) as exc:
        raise PanelApiError(
            "O painel devolveu um resultado final inválido."
        ) from exc

    if final_result.has_human_review:
        raise FinalResultAlreadyReviewedError(
            "Resultados com classificação humana não podem ser reanalisados."
        )

    return final_result
