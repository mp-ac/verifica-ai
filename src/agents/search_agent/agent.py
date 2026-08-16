from langchain.agents import create_agent
from langchain_core.messages import AIMessage

from agents.search_agent.grounding import (
    extract_grounded_sources,
    google_search_executed,
    last_ai_message,
)
from agents.search_agent.observability import build_debug_events, get_used_tools
from agents.search_agent.tools import get_search_tools
from config import SEARCH_AGENT_PROMPT, SEARCH_GOOGLE_SEARCH_ENABLED, SEARCH_PROVIDER
from graph.state import AgentInput
from llm_registry import agent_llm
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage


class IncompleteResearchError(RuntimeError):
    """Raised when the configured online research was not actually executed."""


def _uses_google_search() -> bool:
    return SEARCH_GOOGLE_SEARCH_ENABLED and SEARCH_PROVIDER == "google"


search_agent = create_agent(
    agent_llm,
    tools=get_search_tools(),
    system_prompt=load_prompt(SEARCH_AGENT_PROMPT),
)


def _message_text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content

    return message.text


def _invoke_search(query: str) -> dict:
    return search_agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })


def _retry_google_search(result: dict) -> dict:
    return search_agent.invoke({
        "messages": [
            *result["messages"],
            {
                "role": "user",
                "content": (
                    "A resposta anterior não apresentou comprovação estruturada "
                    "da pesquisa. Execute o Google Search agora e responda somente "
                    "com conclusões sustentadas pelas fontes citadas pelo grounding."
                ),
            },
        ]
    })


def query_search(state: AgentInput) -> dict:
    """Query the Search Agent."""
    query = state.get("research_query", state["query"])
    result = _invoke_search(query)
    retried = False

    if _uses_google_search():
        sources = extract_grounded_sources(result["messages"])
        if not google_search_executed(result["messages"]) or not sources:
            result = _retry_google_search(result)
            retried = True
            sources = extract_grounded_sources(result["messages"])

        if not google_search_executed(result["messages"]):
            raise IncompleteResearchError(
                "O Gemini não apresentou evidência de execução do Google Search."
            )
        if not sources:
            raise IncompleteResearchError(
                "O Gemini executou o Google Search, mas não citou fontes no grounding."
            )
    else:
        sources = []

    final_message = last_ai_message(result["messages"])
    if final_message is None:
        raise IncompleteResearchError("O agente de busca não devolveu uma resposta.")

    debug_events = build_debug_events(result["messages"])
    if retried:
        debug_events.insert(
            1,
            "Agente de busca repetiu a pesquisa por falta de grounding completo.",
        )

    return {
        "results": [{
            "source": "search_agent",
            "result": _message_text(final_message),
        }],
        "sources": sources,
        "tools": get_used_tools(result["messages"]),
        "model_usage": [{
            "role": "search",
            **get_token_usage(result["messages"]),
        }],
        "debug_events": debug_events,
    }
