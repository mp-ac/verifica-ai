from collections.abc import Iterable

from langchain_core.messages import AIMessage


TOKEN_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "thinking_tokens",
    "cached_input_tokens",
    "total_tokens",
)


def empty_token_usage() -> dict[str, int]:
    """Return an empty token usage accumulator."""
    return {field: 0 for field in TOKEN_USAGE_FIELDS}


def get_token_usage(messages: Iterable[object]) -> dict[str, int]:
    """Sum token usage reported in LangChain AI messages."""
    total = empty_token_usage()

    for message in messages:
        if not isinstance(message, AIMessage) or not message.usage_metadata:
            continue

        usage = message.usage_metadata
        input_details = usage.get("input_token_details") or {}
        output_details = usage.get("output_token_details") or {}

        total["input_tokens"] += usage.get("input_tokens", 0)
        total["output_tokens"] += usage.get("output_tokens", 0)
        total["thinking_tokens"] += output_details.get("reasoning", 0)
        total["cached_input_tokens"] += input_details.get("cache_read", 0)
        total["total_tokens"] += usage.get("total_tokens", 0)

    return total
