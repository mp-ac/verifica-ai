from agents.youtube_agent.schemas import YouTubeAnalysisResult
from agents.youtube_agent.tools import YouTubeMetadata


MAX_RESEARCH_CONTEXT_SEGMENTS = 3
MAX_RESEARCH_SUMMARY_CHARS = 400


def _compact_summary(value: str) -> str:
    summary = " ".join(value.split())
    if len(summary) <= MAX_RESEARCH_SUMMARY_CHARS:
        return summary
    return f"{summary[:MAX_RESEARCH_SUMMARY_CHARS - 1].rstrip()}…"


def format_research_context(analysis: YouTubeAnalysisResult) -> str:
    """Format a compact video context for the online research step."""
    relevant_summaries = []
    for item in analysis.relevant_segments:
        summary = _compact_summary(item.relevance)
        if summary:
            relevant_summaries.append(summary)
        if len(relevant_summaries) == MAX_RESEARCH_CONTEXT_SEGMENTS:
            break

    return "\n".join(f"- {summary}" for summary in relevant_summaries)


def format_analysis(
    analysis: YouTubeAnalysisResult,
    metadata: YouTubeMetadata,
) -> str:
    """Format only the video context relevant to the chosen central claim."""
    segments = []
    for item in analysis.relevant_segments:
        details = [f"- Timestamp: {item.timestamp}"]
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
