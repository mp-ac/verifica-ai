from langgraph.graph import END, START, StateGraph

from agents.search_agent import query_search
from agents.transcription_agent import query_transcription
from agents.image_agent import query_image
from graph.nodes import (
    classify_query,
    prepare_search_query,
    route_to_agents,
    synthesize_results,
)
from graph.state import RouterState


workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("search_agent", query_search)
    .add_node("transcription_agent", query_transcription)
    .add_node("image_agent", query_image)
    .add_node("prepare_search", prepare_search_query)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route_to_agents, [
        "search_agent", "transcription_agent", "image_agent",
    ])
    .add_edge("transcription_agent", "prepare_search")
    .add_edge("image_agent", "prepare_search")
    .add_edge("prepare_search", "search_agent")
    .add_edge("search_agent", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
