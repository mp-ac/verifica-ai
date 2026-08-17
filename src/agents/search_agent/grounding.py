from langchain_core.messages import AIMessage

from graph.state import SourceItem


def last_ai_message(agent_messages: list) -> AIMessage | None:
    """Return the last model response emitted by the search agent."""
    return next(
        (
            message
            for message in reversed(agent_messages)
            if isinstance(message, AIMessage)
        ),
        None,
    )


def get_grounding_metadata(agent_messages: list) -> dict:
    """Return Gemini grounding metadata from the last model response."""
    message = last_ai_message(agent_messages)
    if message is None:
        return {}

    metadata = message.response_metadata.get("grounding_metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def extract_grounded_sources(agent_messages: list) -> list[SourceItem]:
    """Extract only web sources cited by Gemini's grounding supports."""
    grounding = get_grounding_metadata(agent_messages)
    chunks = grounding.get("grounding_chunks") or []
    supports = grounding.get("grounding_supports") or []
    cited_indices = {
        index
        for support in supports
        if isinstance(support, dict)
        for index in (support.get("grounding_chunk_indices") or [])
        if isinstance(index, int)
    }

    sources = []
    seen_urls = set()
    for index, chunk in enumerate(chunks):
        if index not in cited_indices or not isinstance(chunk, dict):
            continue

        web = chunk.get("web")
        if not isinstance(web, dict):
            continue

        url = str(web.get("uri") or "").strip()
        if not url or url in seen_urls:
            continue

        title = str(web.get("title") or url).strip()
        seen_urls.add(url)
        sources.append(SourceItem(title=title, url=url))

    return sources


def google_search_executed(agent_messages: list) -> bool:
    """Check whether Gemini reports at least one executed web query."""
    grounding = get_grounding_metadata(agent_messages)
    return bool(grounding.get("web_search_queries"))
