from langchain_core.messages import HumanMessage

from config import YOUTUBE_AGENT_PROMPT
from graph.state import AgentInput, Attachment, YouTubeAnalysisResult
from llm_registry import youtube_llm
from llm_settings import get_youtube_settings
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


def _format_analysis(analysis: YouTubeAnalysisResult) -> str:
    """Format video findings as factual context for the search agent."""
    claims = []
    for item in analysis.claims:
        details = [
            f"- Timestamp: {item.timestamp}",
            f"  Alegação: {item.claim}",
        ]
        if item.spoken_excerpt:
            details.append(f"  Trecho falado: {item.spoken_excerpt}")
        if item.visual_context:
            details.append(f"  Contexto visual: {item.visual_context}")
        claims.append("\n".join(details))

    formatted_claims = "\n".join(claims)
    if not formatted_claims:
        formatted_claims = "- Nenhuma alegação factual explícita foi identificada."

    limitations = "\n".join(
        f"- {limitation}"
        for limitation in analysis.limitations
    )
    if not limitations:
        limitations = "- Nenhuma limitação adicional informada."

    return (
        f"Resumo do vídeo:\n{analysis.summary}\n\n"
        f"Alegações identificadas:\n{formatted_claims}\n\n"
        f"Consulta sugerida para pesquisa:\n{analysis.research_query}\n\n"
        f"Limitações da análise do vídeo:\n{limitations}"
    )


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

    structured_llm = youtube_llm.with_structured_output(
        YouTubeAnalysisResult,
        include_raw=True,
    )
    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(YOUTUBE_AGENT_PROMPT),
        },
        HumanMessage(content=[
            {
                "type": "text",
                "text": (
                    "Analise o vídeo como objeto de verificação factual. "
                    "Considere o pedido original abaixo apenas para definir o "
                    "foco da análise.\n\n"
                    f"<pedido_original>\n{state['query']}\n</pedido_original>"
                ),
            },
            {
                "type": "media",
                "file_uri": str(attachment.url),
                "mime_type": "video/mp4",
            },
        ]),
    ])
    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    return {
        "media_contexts": [{
            "source": "youtube_agent",
            "result": _format_analysis(response["parsed"]),
        }],
        "model_usage": [{
            "role": "youtube",
            **get_token_usage([response["raw"]]),
        }],
        "debug_events": [
            "Agente do YouTube analisou áudio e vídeo e preparou a pesquisa."
        ],
    }
