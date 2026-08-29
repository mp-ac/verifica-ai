from langgraph.graph import END, START, StateGraph

from agents.search_agent import query_search
from agents.transcription_agent import query_transcription
from agents.image_agent import query_image
from agents.image_authenticity_agent import query_image_authenticity
from agents.youtube_agent import query_youtube
from graph.nodes import (
    classify_query,
    prepare_human_response,
    prepare_search_query,
    route_after_prepare_search,
    route_to_agents,
    synthesize_results,
)
from graph.state import RouterState


workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("human_response", prepare_human_response)
    .add_node("search_agent", query_search)
    .add_node("transcription_agent", query_transcription)
    .add_node("image_agent", query_image)
    .add_node("image_authenticity_agent", query_image_authenticity)
    .add_node("youtube_agent", query_youtube)
    .add_node("prepare_search", prepare_search_query)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route_to_agents, [
        "search_agent", "transcription_agent", "image_agent",
        "image_authenticity_agent", "youtube_agent",
        "human_response",
    ])
    .add_edge("human_response", END)
    .add_edge("transcription_agent", "prepare_search")
    .add_edge("image_agent", "prepare_search")
    .add_edge("image_authenticity_agent", "prepare_search")
    .add_edge("youtube_agent", "prepare_search")
    .add_conditional_edges(
        "prepare_search",
        route_after_prepare_search,
        {
            "search_agent": "search_agent",
            "human_response": "human_response",
            "end": END,
        },
    )
    .add_edge("search_agent", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
