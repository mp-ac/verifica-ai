from langgraph.graph import END, START, StateGraph

from agents.search_agent import query_search
from graph.nodes import classify_query, route_to_agents, synthesize_results
from graph.state import RouterState


workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("search_agent", query_search)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route_to_agents, ["search_agent"])
    .add_edge("search_agent", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
