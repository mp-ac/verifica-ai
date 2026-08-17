from collections.abc import Iterable

from graph.state import SourceItem


def deduplicate_sources(sources: Iterable[SourceItem]) -> list[SourceItem]:
    """Remove duplicate source URLs while preserving their original order."""
    unique_sources = []
    seen_urls = set()

    for source in sources:
        url = source.url.strip()
        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        unique_sources.append(source)

    return unique_sources


def select_allowed_sources(
    requested_sources: Iterable[SourceItem],
    allowed_sources: Iterable[SourceItem],
    *,
    max_items: int = 10,
) -> list[SourceItem]:
    """Keep the model's selected sources only when their URLs are allowed."""
    allowed = deduplicate_sources(allowed_sources)
    allowed_by_url = {
        source.url.strip(): source
        for source in allowed
    }
    selected = []
    seen_urls = set()

    for source in requested_sources:
        url = source.url.strip()
        if url in seen_urls or url not in allowed_by_url:
            continue

        seen_urls.add(url)
        selected.append(allowed_by_url[url])
        if len(selected) == max_items:
            break

    if selected:
        return selected

    return allowed[:max_items]
