from langchain_core.messages import AIMessage, ToolMessage

from agents.search_agent.grounding import (
    extract_grounded_sources,
    get_grounding_metadata,
    google_search_executed,
)


def build_debug_events(agent_messages: list) -> list[str]:
    """Build execution events from the search agent messages."""
    events = ["Agente de busca recebeu a tarefa do router."]

    if google_search_executed(agent_messages):
        grounding = get_grounding_metadata(agent_messages)
        query_count = len(grounding.get("web_search_queries") or [])
        source_count = len(extract_grounded_sources(agent_messages))
        events.append(
            "Google Search executou "
            f"{query_count} consulta(s) e citou {source_count} fonte(s)."
        )

    for message in agent_messages:
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                events.append(
                    f"Ferramenta chamada: {tool_call['name']} | args: {tool_call['args']}"
                )
        elif isinstance(message, ToolMessage):
            tool_name = message.name or "unknown_tool"
            preview = str(message.content).strip().replace("\n", " ")
            if len(preview) > 180:
                preview = preview[:177] + "..."
            events.append(f"Ferramenta retornou: {tool_name} | preview: {preview}")

    events.append("Agente de busca concluiu a resposta.")
    return events


def get_used_tools(agent_messages: list) -> list[str]:
    """Return unique names of tools proven to have executed."""
    used_tools = {
        message.name
        for message in agent_messages
        if isinstance(message, ToolMessage) and message.name
    }
    if google_search_executed(agent_messages):
        used_tools.add("google_search")

    return sorted(used_tools)
