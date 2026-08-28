from langgraph.graph import END, START, StateGraph

from agents.image_agent import query_image
from agents.image_authenticity_agent import query_image_authenticity
from agents.search_agent import query_search
from agents.transcription_agent import query_transcription
from agents.youtube_agent import query_youtube
from reanalysis.graph.nodes import (
    prepare_reanalysis_search,
    route_after_prepare_reanalysis,
    route_reanalysis,
    synthesize_reanalysis,
)
from reanalysis.graph.state import ReanalysisState


reanalysis_workflow = (
    StateGraph(ReanalysisState)
    .add_node("search_agent", query_search)
    .add_node("transcription_agent", query_transcription)
    .add_node("image_agent", query_image)
    .add_node("image_authenticity_agent", query_image_authenticity)
    .add_node("youtube_agent", query_youtube)
    .add_node("prepare_search", prepare_reanalysis_search)
    .add_node("synthesize", synthesize_reanalysis)
    .add_conditional_edges(
        START,
        route_reanalysis,
        [
            "search_agent",
            "transcription_agent",
            "image_agent",
            "image_authenticity_agent",
            "youtube_agent",
        ],
    )
    .add_edge("transcription_agent", "prepare_search")
    .add_edge("image_agent", "prepare_search")
    .add_edge("image_authenticity_agent", "prepare_search")
    .add_edge("youtube_agent", "prepare_search")
    .add_conditional_edges(
        "prepare_search",
        route_after_prepare_reanalysis,
        {"search_agent": "search_agent", "end": END},
    )
    .add_edge("search_agent", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
