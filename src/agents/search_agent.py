import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage

from graph.state import AgentInput
from llms import agent_llm
from tools.current_date import current_date
from tools.fetch_url import fetch_url
from tools.get_links import get_links
from util import load_prompt

load_dotenv()

search_agent = create_agent(
    agent_llm,
    tools=[current_date, get_links, fetch_url],
    system_prompt=load_prompt(os.getenv('SEARCH_AGENT_PROMPT')),
)


def _build_debug_events(agent_messages: list) -> list[str]:
    events = ["Agente de busca recebeu a tarefa do router."]

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


def query_search(state: AgentInput) -> dict:
    """Query the Search Agent."""
    result = search_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    return {
        "results": [{"source": "search_agent", "result": result["messages"][-1].content}],
        "debug_events": _build_debug_events(result["messages"]),
    }
