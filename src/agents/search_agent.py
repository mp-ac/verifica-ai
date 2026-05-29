from llms import agent_llm
from tools.current_date import current_date
from tools.fetch_url import fetch_url
from tools.get_links import get_links
from util import load_system_prompt
from langchain.agents import create_agent
from graph.state import AgentInput

search_agent = create_agent(
    agent_llm,
    tools=[current_date, get_links, fetch_url],
    system_prompt=load_system_prompt(),
)


def query_search(state: AgentInput) -> dict:
    """Query the Search Agent."""
    result = search_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    return {"results": [{"source": "search_agent", "result": result["messages"][-1].content}]}
