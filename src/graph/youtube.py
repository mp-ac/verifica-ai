from graph.state import FinalAnswerResult


def format_youtube_research_query(
    central_claim: str,
    relevant_context: str = "",
) -> str:
    """Build a deterministic search brief for one YouTube claim."""
    parts = [
        "Verifique exclusivamente esta alegação central do vídeo:",
        f'"{central_claim.strip()}"',
    ]
    if relevant_context.strip():
        parts.extend([
            "Contexto essencial do vídeo diretamente relacionado à alegação:",
            relevant_context.strip(),
        ])
    parts.append(
        "Pesquise evidências que confirmem, contradigam ou contextualizem "
        "essa formulação exata. Não transforme informações de apoio, "
        "opiniões ou outros assuntos do vídeo em alegações independentes."
    )
    return "\n\n".join(parts)


def build_youtube_clarification_answer(reason: str | None) -> FinalAnswerResult:
    """Return the deterministic handoff used when a video has no safe focus."""
    explanation = (
        "O vídeo apresenta vários assuntos independentes e o usuário não "
        "informou qual deles deseja verificar. Oriente o usuário a indicar a "
        "afirmação, o trecho ou o timestamp que deve ser analisado."
    )
    if reason:
        explanation = f"{explanation}\n\nMotivo identificado: {reason.strip()}"

    return FinalAnswerResult(
        title="Esclarecimento necessário para analisar o vídeo",
        answer=(
            "Não há uma alegação factual classificável.\n\n"
            f"{explanation}"
        ),
        sources=[],
        classification=None,
    )
