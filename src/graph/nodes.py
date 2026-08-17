from langgraph.types import Send

from config import ROUTER_CLASSIFICATION_PROMPT, ROUTER_SYNTHESIS_PROMPT
from graph.state import ClassificationResult, FinalAnswerResult, RouterState, SourceItem
from llm_registry import router_llm
from utils.prompts_util import load_prompt
from utils.sources import deduplicate_sources, select_allowed_sources
from utils.title_formatting import format_classified_title
from utils.token_usage import get_token_usage
from utils.youtube_research import (
    build_youtube_clarification_answer,
    format_youtube_research_query,
)


MEDIA_AGENT_BY_TYPE = {
    "image": "image_agent",
    "audio": "transcription_agent",
    "video": "transcription_agent",
    "youtube": "youtube_agent",
}


def _format_input_for_search(
    state: RouterState,
    *,
    excluded_media_sources: set[str] | None = None,
    fallback: str = "Analise os conteúdos enviados pelo usuário.",
) -> str:
    """Combine the original text, web links and extracted media contexts."""
    excluded_media_sources = excluded_media_sources or set()
    query = state["query"]
    attachments = state.get("attachments", [])

    for attachment in attachments:
        if attachment.get("type") in MEDIA_AGENT_BY_TYPE:
            query = query.replace(str(attachment["url"]), "")

    parts = []
    if query.strip():
        parts.append(f"Mensagem original do usuário:\n{query.strip()}")

    web_links = [
        str(attachment["url"])
        for attachment in attachments
        if attachment.get("type") in {"web", "unknown"}
    ]
    if web_links:
        parts.append(
            "Links enviados pelo usuário:\n"
            + "\n".join(f"- {url}" for url in web_links)
        )

    media_contexts = [
        context
        for context in state.get("media_contexts", [])
        if context["source"] not in excluded_media_sources
    ]
    if media_contexts:
        parts.append(
            "Conteúdo extraído das mídias enviadas:\n"
            + "\n\n".join(
                f"[{context['source']}]\n{context['result']}"
                for context in media_contexts
            )
        )

    return "\n\n".join(parts) or fallback


def classify_query(state: RouterState) -> dict:
    """Classify query and determine which agents to invoke."""
    attachments = state.get("attachments", [])
    media_classifications = [
        {
            "source": MEDIA_AGENT_BY_TYPE[attachment["type"]],
            "query": state["query"],
            "attachment": attachment,
        }
        for attachment in attachments
        if attachment.get("type") in MEDIA_AGENT_BY_TYPE
    ]

    if media_classifications:
        return {
            "classifications": media_classifications,
            "debug_events": [
                (
                    "Router identificou "
                    f"{len(media_classifications)} mídia(s) para processamento."
                ),
                "Router encaminhou as mídias aos agentes especializados.",
            ],
        }

    if attachments:
        search_query = _format_input_for_search(state)
        return {
            "classifications": [{
                "source": "search_agent",
                "query": search_query,
            }],
            "debug_events": [
                "Router encaminhou os links recebidos ao agente de busca."
            ],
        }

    structured_llm = router_llm.with_structured_output(
        ClassificationResult,
        include_raw=True,
    )

    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(ROUTER_CLASSIFICATION_PROMPT)

        },
        {"role": "user", "content": state["query"]}
    ])

    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    result = response["parsed"]
    return {
        "classifications": result.classifications,
        "model_usage": [{
            "role": "router",
            **get_token_usage([response["raw"]]),
        }],
        "debug_events": [
            f"Router interpretou a pergunta original: {state['query']}",
            f"Router decidiu as rotas: {[c['source'] for c in result.classifications]}",
        ],
    }


def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    sends = []
    for classification in state["classifications"]:
        agent_input = {"query": classification["query"]}
        if "attachment" in classification:
            agent_input["attachment"] = classification["attachment"]
        sends.append(Send(classification["source"], agent_input))

    return sends


def prepare_search_query(state: RouterState) -> dict:
    """Prepare one consolidated search after all media has been processed."""
    if state.get("youtube_requires_clarification"):
        return {
            "final_answer": build_youtube_clarification_answer(
                state.get("youtube_clarification_reason")
            ),
            "debug_events": [
                "Análise encerrada sem pesquisa porque o vídeo não possui "
                "um foco factual único."
            ],
        }

    central_claim = state.get("youtube_central_claim")
    if central_claim:
        youtube_context = next(
            (
                context["result"]
                for context in state.get("media_contexts", [])
                if context["source"] == "youtube_agent"
            ),
            "Nenhum contexto adicional foi extraído.",
        )
        research_query = format_youtube_research_query(
            central_claim,
            youtube_context,
        )
        additional_context = _format_input_for_search(
            state,
            excluded_media_sources={"youtube_agent"},
            fallback="",
        )
        if additional_context:
            research_query = "\n\n".join([
                research_query,
                "Outros conteúdos enviados para a mesma análise:",
                additional_context,
            ])
    else:
        research_query = _format_input_for_search(state)

    return {
        "research_query": research_query,
        "debug_events": [
            "A alegação central e o contexto relevante foram preparados para "
            "pesquisa online."
        ],
    }


def route_after_prepare_search(state: RouterState) -> str:
    """Skip research and synthesis when the user must clarify the video."""
    if state.get("final_answer") is not None:
        return "end"
    return "search_agent"


def synthesize_results(state: RouterState) -> dict:
    """Combine results from all agents into a titled, coherent answer."""
    if not state["results"]:
        return {
            "final_answer": FinalAnswerResult(
                title="Nenhum resultado encontrado",
                answer="Nenhum resultado foi encontrado",
                sources=[
                    SourceItem(
                        title="Sem fontes disponíveis",
                        url=""
                    )
                ],
                classification=None,
            ),
            "debug_events": ["Nenhum resultado foi devolvido pelos agentes."],
        }

    formatted = [
        f"**From {r['source'].title()}:**\n{r['result']}"
        for r in state["results"]
    ]

    structured_llm = router_llm.with_structured_output(
        FinalAnswerResult,
        include_raw=True,
    )

    response = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(ROUTER_SYNTHESIS_PROMPT).format(
                query=state["query"]
            )
        },
        {"role": "user", "content": "\n\n".join(formatted)}
    ])

    if response["parsing_error"] is not None:
        raise response["parsing_error"]

    final_answer = response["parsed"]
    grounded_sources = deduplicate_sources(state.get("sources", []))
    if grounded_sources:
        final_answer.sources = select_allowed_sources(
            final_answer.sources,
            grounded_sources,
        )
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
        "debug_events": ["Router sintetizou a resposta final a partir dos resultados do agente."],
    }
