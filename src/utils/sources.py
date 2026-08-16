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
