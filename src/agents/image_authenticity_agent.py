"""Optional visual assessment of whether an image may be AI-generated."""

import logging

from langchain_core.messages import HumanMessage

from config import IMAGE_AUTHENTICITY_PROMPT
from graph.state import AgentInput, Attachment
from image_authenticity import (
    ImageAuthenticityAnalysis,
    ImageAuthenticityModelResult,
)
from llm_registry import image_llm
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


logger = logging.getLogger(__name__)


def _unavailable_analysis(attachment_index: int) -> ImageAuthenticityAnalysis:
    """Build a safe fail-open result when the optional assessment fails."""
    return ImageAuthenticityAnalysis(
        attachment_index=attachment_index,
        status="unavailable",
        assessment="inconclusive",
        confidence=None,
        limitations=[
            "A análise de autenticidade da imagem não pôde ser concluída."
        ],
    )


def query_image_authenticity(state: AgentInput) -> dict:
    """Assess one image without blocking the factual-verification workflow."""
    attachment = Attachment.model_validate(state.get("attachment"))
    if attachment.type != "image":
        raise ValueError(
            "O agente de autenticidade recebeu um attachment inválido."
        )

    attachment_index = state.get("attachment_index")
    if not isinstance(attachment_index, int) or attachment_index < 0:
        raise ValueError(
            "O agente de autenticidade recebeu um índice de attachment inválido."
        )

    try:
        structured_llm = image_llm.with_structured_output(
            ImageAuthenticityModelResult,
            include_raw=True,
        )
        response = structured_llm.invoke([
            {
                "role": "system",
                "content": load_prompt(IMAGE_AUTHENTICITY_PROMPT),
            },
            HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "Avalie probabilisticamente se esta imagem apresenta "
                            "sinais visuais de geração por inteligência artificial."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": str(attachment.url)},
                    },
                ]
            ),
        ])
        if response["parsing_error"] is not None:
            raise response["parsing_error"]

        analysis = ImageAuthenticityAnalysis(
            attachment_index=attachment_index,
            status="completed",
            **response["parsed"].model_dump(),
        )
        return {
            "image_authenticity_analyses": [analysis],
            "model_usage": [{
                "role": "image",
                **get_token_usage([response["raw"]]),
            }],
            "debug_events": [
                "Agente avaliou sinais visuais de geração artificial na imagem."
            ],
        }
    except Exception as exc:
        logger.warning(
            "Análise opcional de autenticidade indisponível: error_type=%s",
            type(exc).__name__,
        )
        return {
            "image_authenticity_analyses": [
                _unavailable_analysis(attachment_index)
            ],
            "debug_events": [
                "Análise de autenticidade indisponível; fluxo principal mantido."
            ],
        }
