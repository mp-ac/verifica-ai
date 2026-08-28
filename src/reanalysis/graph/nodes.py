from langgraph.types import Send

from config import REANALYSIS_SYNTHESIS_PROMPT
from graph.state import FinalAnswerResult
from graph.youtube import (
    build_youtube_clarification_answer,
    format_youtube_research_query,
)
from llm_registry import router_llm
from reanalysis.graph.state import ReanalysisState
from utils.prompts_util import load_prompt
from utils.sources import deduplicate_sources
from utils.title_formatting import format_classified_title
from utils.token_usage import get_token_usage


MEDIA_AGENT_BY_TYPE = {
    "image": "image_agent",
    "audio": "transcription_agent",
    "video": "transcription_agent",
    "youtube": "youtube_agent",
}


def _format_sources(final_answer: FinalAnswerResult) -> str:
    if not final_answer.sources:
        return "- Nenhuma fonte registrada."

    return "\n".join(
        f"- {source.title}: {source.url}"
        for source in final_answer.sources
    )


def _format_attachments(state: ReanalysisState) -> str:
    attachments = state.get("attachments", [])
    if not attachments:
        return "- Nenhum anexo registrado."

    return "\n".join(
        f"- [{attachment.type}] {attachment.url}"
        for attachment in attachments
    )


def format_reanalysis_research_query(state: ReanalysisState) -> str:
    original = state["original_final_answer"]
    parts = [
        "<consulta_original>",
        state["query"],
        "</consulta_original>",
        "<resultado_anterior>",
        f"Título: {original.title}",
        f"Classificação: {original.classification or 'null'}",
        f"Resposta:\n{original.answer}",
        f"Fontes:\n{_format_sources(original)}",
        "</resultado_anterior>",
        "<instrucao_do_analista>",
        state["prompt"],
        "</instrucao_do_analista>",
        "<anexos_originais>",
        _format_attachments(state),
        "</anexos_originais>",
    ]

    media_contexts = state.get("media_contexts", [])
    central_claim = state.get("youtube_central_claim")
    if central_claim:
        parts.extend([
            "<foco_central_do_video>",
            format_youtube_research_query(
                central_claim,
                state.get("youtube_research_context", ""),
            ),
            "</foco_central_do_video>",
        ])
        media_contexts = [
            context
            for context in media_contexts
            if context["source"] != "youtube_agent"
        ]

    if media_contexts:
        parts.extend([
            "<conteudo_extraido_das_midias>",
            "\n\n".join(
                f"[{context['source']}]\n{context['result']}"
                for context in media_contexts
            ),
            "</conteudo_extraido_das_midias>",
        ])

    parts.append(
        "Pesquise a lacuna apontada pelo analista e produza evidências para "
        "melhorar o resultado anterior sem ignorar o que ele já contém."
    )
    return "\n\n".join(parts)


def route_reanalysis(state: ReanalysisState) -> list[Send]:
    media_sends = []
    for attachment_index, attachment in enumerate(
        state.get("attachments", [])
    ):
        if attachment.type not in MEDIA_AGENT_BY_TYPE:
            continue

        agent_input = {
            "query": state["prompt"],
            "attachment": attachment.model_dump(mode="json"),
            "attachment_index": attachment_index,
        }
        media_sends.append(Send(
            MEDIA_AGENT_BY_TYPE[attachment.type],
            agent_input,
        ))
        if attachment.type == "image":
            media_sends.append(Send(
                "image_authenticity_agent",
                agent_input,
            ))
    if media_sends:
        return media_sends

    return [
        Send(
            "search_agent",
            {"query": format_reanalysis_research_query(state)},
        )
    ]


def prepare_reanalysis_search(state: ReanalysisState) -> dict:
    if state.get("youtube_requires_clarification"):
        return {
            "final_answer": build_youtube_clarification_answer(
                state.get("youtube_clarification_reason")
            ),
            "debug_events": [
                "Reanálise encerrada sem pesquisa porque o vídeo não possui "
                "um foco factual único."
            ],
        }

    return {
        "research_query": format_reanalysis_research_query(state),
        "debug_events": [
            "O contexto original e a instrução humana foram preparados "
            "para pesquisa."
        ],
    }


def route_after_prepare_reanalysis(state: ReanalysisState) -> str:
    """Skip research when the video still needs a precise human instruction."""
    if state.get("final_answer") is not None:
        return "end"
    return "search_agent"


def _format_reanalysis_synthesis_input(
    state: ReanalysisState,
    research_results: str,
) -> str:
    original = state["original_final_answer"]
    return "\n\n".join([
        "<consulta_original>",
        state["query"],
        "</consulta_original>",
        "<resultado_anterior>",
        f"Título: {original.title}",
        f"Classificação: {original.classification or 'null'}",
        f"Resposta:\n{original.answer}",
        f"Fontes:\n{_format_sources(original)}",
        "</resultado_anterior>",
        "<instrucao_do_analista>",
        state["prompt"],
        "</instrucao_do_analista>",
        "<resultados_da_nova_pesquisa>",
        research_results,
        "</resultados_da_nova_pesquisa>",
    ])


def synthesize_reanalysis(state: ReanalysisState) -> dict:
    research_results = "\n\n".join(
        f"**From {result['source'].title()}:**\n{result['result']}"
        for result in state.get("results", [])
    )
    if not research_results:
        research_results = "Nenhum resultado novo foi devolvido pelos agentes."

    structured_llm = router_llm.with_structured_output(
        FinalAnswerResult,
        include_raw=True,
    )
    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(REANALYSIS_SYNTHESIS_PROMPT),
        },
        {
            "role": "user",
            "content": _format_reanalysis_synthesis_input(
                state,
                research_results,
            ),
        },
    ])

    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    final_answer = response["parsed"]
    grounded_sources = state.get("sources", [])
    if grounded_sources:
        final_answer.sources = deduplicate_sources([
            *state["original_final_answer"].sources,
            *grounded_sources,
        ])
    final_answer.title = format_classified_title(
        final_answer.title,
        final_answer.classification,
    )

    return {
        "final_answer": final_answer,
        "model_usage": [{
            "role": "router",
            **get_token_usage([response["raw"]]),
        }],
        "debug_events": [
            "O router consolidou o resultado anterior com a nova pesquisa."
        ],
    }
