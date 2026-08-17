from langchain_core.messages import HumanMessage

from config import YOUTUBE_AGENT_PROMPT
from agents.youtube_agent.tools import (
    YouTubeMetadata,
    YouTubeMetadataError,
    get_youtube_metadata,
)
from graph.state import AgentInput, Attachment, YouTubeAnalysisResult
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
        HumanMessage(content=_build_message_content(
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
            "result": _format_analysis(analysis, metadata),
        }],
        **(
            {"youtube_central_claim": analysis.central_claim}
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


def _build_message_content(
    *,
    query: str,
    video_url: str,
    metadata: YouTubeMetadata,
) -> list[dict]:
    title = metadata.title or "INDISPONÍVEL"
    content = [{
        "type": "text",
        "text": (
            "Analise o vídeo como objeto de verificação factual. O título "
            "abaixo foi obtido diretamente dos metadados públicos do YouTube "
            "e é a única fonte autoritativa para o título do vídeo.\n\n"
            f"<titulo_oficial_youtube>\n{title}\n</titulo_oficial_youtube>\n\n"
            f"<pedido_original>\n{query}\n</pedido_original>\n\n"
            "Se houver uma imagem anexada antes do vídeo, ela é a thumbnail "
            "oficial e deve ser usada somente conforme as regras do prompt."
        ),
    }]
    if metadata.thumbnail_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": metadata.thumbnail_url},
        })
    content.append({
        "type": "media",
        "file_uri": video_url,
        "mime_type": "video/mp4",
    })
    return content


def _format_analysis(
    analysis: YouTubeAnalysisResult,
    metadata: YouTubeMetadata,
) -> str:
    """Format only the video context relevant to the chosen central claim."""
    segments = []
    for item in analysis.relevant_segments:
        details = [
            f"- Timestamp: {item.timestamp}",
        ]
        if item.spoken_excerpt:
            details.append(f"  Trecho falado: {item.spoken_excerpt}")
        if item.visual_context:
            details.append(f"  Contexto visual: {item.visual_context}")
        details.append(f"  Relevância: {item.relevance}")
        segments.append("\n".join(details))

    formatted_segments = "\n".join(segments)
    if not formatted_segments:
        formatted_segments = "- Nenhum trecho relevante pôde ser extraído."

    limitations = "\n".join(
        f"- {limitation}"
        for limitation in analysis.limitations
    )
    if not limitations:
        limitations = "- Nenhuma limitação adicional informada."

    clarification = analysis.clarification_reason or "Não necessário"

    return (
        f"Título oficial do vídeo: {metadata.title or 'Não disponível'}\n"
        f"Contexto da thumbnail: "
        f"{analysis.thumbnail_context or 'Não utilizado'}\n\n"
        f"Alegação central: {analysis.central_claim or 'Não definida'}\n"
        f"Origem do foco: {analysis.central_claim_source or 'Não definida'}\n\n"
        f"Esclarecimento necessário: {clarification}\n\n"
        f"Trechos relevantes:\n{formatted_segments}\n\n"
        f"Limitações da análise do vídeo:\n{limitations}"
    )
