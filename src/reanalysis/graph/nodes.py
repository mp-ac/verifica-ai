from langgraph.types import Send

from config import REANALYSIS_SYNTHESIS_PROMPT
from graph.state import FinalAnswerResult
from llm_registry import router_llm
from reanalysis.graph.state import ReanalysisState
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


MEDIA_AGENT_BY_TYPE = {
    "image": "image_agent",
    "audio": "transcription_agent",
    "video": "transcription_agent",
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
    media_sends = [
        Send(
            MEDIA_AGENT_BY_TYPE[attachment.type],
            {
                "query": state["prompt"],
                "attachment": attachment.model_dump(mode="json"),
            },
        )
        for attachment in state.get("attachments", [])
        if attachment.type in MEDIA_AGENT_BY_TYPE
    ]
    if media_sends:
        return media_sends

    return [
        Send(
            "search_agent",
            {"query": format_reanalysis_research_query(state)},
        )
    ]


def prepare_reanalysis_search(state: ReanalysisState) -> dict:
    return {
        "research_query": format_reanalysis_research_query(state),
        "debug_events": [
            "O contexto original e a instrução humana foram preparados "
            "para pesquisa."
        ],
    }


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

    return {
        "final_answer": response["parsed"],
        "model_usage": [{
            "role": "router",
            **get_token_usage([response["raw"]]),
        }],
        "debug_events": [
            "O router consolidou o resultado anterior com a nova pesquisa."
        ],
    }
