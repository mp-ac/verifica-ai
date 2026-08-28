from graph.state import FinalAnswerResult
from utils.title_formatting import strip_classification_prefix


def build_duplicate_check_query(
    final_answer: FinalAnswerResult | None,
) -> str | None:
    """Return the normalized final title used to search for duplicates."""
    if final_answer is None:
        return None

    normalized_title = strip_classification_prefix(final_answer.title)
    return normalized_title or None
