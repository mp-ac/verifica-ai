import re

from graph.state import ClassificationLabel


TITLE_PREFIXES: dict[ClassificationLabel, str] = {
    "verdadeiro": "VERDADEIRO",
    "falso": "FALSO",
    "enganoso": "ENGANOSO",
    "inconclusivo": "INCONCLUSIVO",
}

_EXISTING_PREFIX_PATTERN = re.compile(
    r"^\s*#?(?:VERDADEIRO|FALSO|ENGANOSO|INCONCLUSIVO)\s*:\s*",
    flags=re.IGNORECASE,
)


def strip_classification_prefix(title: str) -> str:
    """Return a title without a leading structured verdict prefix."""
    return _EXISTING_PREFIX_PATTERN.sub("", title).strip()


def format_classified_title(
    title: str,
    classification: ClassificationLabel | None,
) -> str:
    """Add the structured verdict to a title without duplicating prefixes."""
    title_without_prefix = strip_classification_prefix(title)
    if classification is None:
        return title_without_prefix

    prefix = TITLE_PREFIXES[classification]
    if not title_without_prefix:
        return f"{prefix}:"

    return f"{prefix}: {title_without_prefix}"
