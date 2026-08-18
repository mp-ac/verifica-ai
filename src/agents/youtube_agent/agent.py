from langchain_core.messages import HumanMessage

from agents.youtube_agent.formatting import format_analysis, format_research_context
from agents.youtube_agent.message import build_message_content
from agents.youtube_agent.schemas import YouTubeAnalysisResult
from agents.youtube_agent.tools import (
    YouTubeMetadata,
    YouTubeMetadataError,
    get_youtube_metadata,
)
from config import YOUTUBE_AGENT_PROMPT
from graph.state import AgentInput, Attachment
from llm_registry import youtube_llm
from llm_settings import get_youtube_settings
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


def query_youtube(state: AgentInput) -> dict:
    """Analyze one public YouTube video before independent online research."""
    attachment = Attachment.model_validate(state.get("attachment"))
    if attachment.type != "youtube":
        raise ValueError("O agente do YouTube recebeu um attachment inválido.")

    settings = get_youtube_settings()
    if settings.provider != "google":
        raise ValueError(
            "A análise de vídeos do YouTube requer provider google nas "
            "configurações YOUTUBE_* ou no fallback IMAGE_*."
        )

    video_url = str(attachment.url)
    metadata_available = True
    try:
        metadata = get_youtube_metadata(video_url)
    except YouTubeMetadataError:
        metadata = YouTubeMetadata()
        metadata_available = False

    structured_llm = youtube_llm.with_structured_output(
        YouTubeAnalysisResult,
        include_raw=True,
    )
    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(YOUTUBE_AGENT_PROMPT),
        },
        HumanMessage(content=build_message_content(
            query=state["query"],
            video_url=video_url,
            metadata=metadata,
        )),
    ])
    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    analysis = response["parsed"]
    if (
        not metadata_available
        and not analysis.requires_clarification
        and analysis.central_claim_source != "user_query"
    ):
        analysis = YouTubeAnalysisResult(
            requires_clarification=True,
            clarification_reason=(
                "O título e a thumbnail oficiais não puderam ser obtidos, e "
                "o usuário não informou uma alegação específica."
            ),
            limitations=[
                "Os metadados públicos do YouTube estavam indisponíveis."
            ],
        )

    metadata_limitation = (
        "Os metadados públicos do YouTube estavam indisponíveis."
    )
    if (
        not metadata_available
        and metadata_limitation not in analysis.limitations
    ):
        analysis.limitations.append(
            metadata_limitation
        )
    if analysis.requires_clarification:
        debug_event = (
            "Agente do YouTube não encontrou um foco factual único e solicitou "
            "esclarecimento do usuário."
        )
    else:
        debug_event = (
            "Agente do YouTube definiu uma alegação central para pesquisa "
            f"a partir de {analysis.central_claim_source}."
        )

    return {
        "media_contexts": [{
            "source": "youtube_agent",
            "result": format_analysis(analysis, metadata),
        }],
        **(
            {"youtube_central_claim": analysis.central_claim}
            if analysis.central_claim is not None
            else {}
        ),
        **(
            {"youtube_research_context": format_research_context(analysis)}
            if analysis.central_claim is not None
            else {}
        ),
        "youtube_requires_clarification": analysis.requires_clarification,
        **(
            {"youtube_clarification_reason": analysis.clarification_reason}
            if analysis.clarification_reason is not None
            else {}
        ),
        "model_usage": [{
            "role": "youtube",
            **get_token_usage([response["raw"]]),
        }],
        "debug_events": [
            (
                "Agente do YouTube obteve os metadados oficiais do vídeo."
                if metadata_available
                else "Metadados oficiais do YouTube não estavam disponíveis."
            ),
            debug_event,
        ],
    }
