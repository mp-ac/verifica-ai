from config import SEARCH_GOOGLE_SEARCH_ENABLED, SEARCH_PROVIDER

from agents.search_agent.tools.current_date import current_date
from agents.search_agent.tools.fetch_url import fetch_url
from agents.search_agent.tools.get_links import get_links


def get_search_tools() -> list:
    """Select native Gemini search or the local SerpAPI research tools."""
    if SEARCH_GOOGLE_SEARCH_ENABLED:
        if SEARCH_PROVIDER != "google":
            raise ValueError(
                "SEARCH_GOOGLE_SEARCH_ENABLED=true requer SEARCH_PROVIDER=google."
            )
        return [{"google_search": {}}]

    return [current_date, get_links, fetch_url]


__all__ = ["current_date", "fetch_url", "get_links", "get_search_tools"]
