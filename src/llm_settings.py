from dataclasses import dataclass
import os


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1
    timeout: int = 120


def _load_role_settings(
    prefix: str,
    default_temperature: float,
    default_timeout: int = 120,
) -> LLMSettings:
    """Build role-specific LLM settings from environment variables."""
    return LLMSettings(
        provider=os.getenv(f"{prefix}_PROVIDER", "vllm").strip().lower(),
        model=os.getenv(f"{prefix}_MODEL", "").strip(),
        api_key=_get_optional_env(f"{prefix}_API_KEY"),
        base_url=_get_optional_env(f"{prefix}_BASE_URL"),
        temperature=float(
            os.getenv(f"{prefix}_TEMPERATURE", str(default_temperature))
        ),
        timeout=int(os.getenv(f"{prefix}_TIMEOUT", str(default_timeout))),
    )


def _get_optional_env(name: str) -> str | None:
    """Return a stripped environment variable value or None when empty."""
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def get_router_settings() -> LLMSettings:
    """Load router LLM settings from the environment."""
    return _load_role_settings("ROUTER", default_temperature=0.5)


def get_search_settings() -> LLMSettings:
    """Load search LLM settings from the environment."""
    return _load_role_settings("SEARCH", default_temperature=0.1)


def get_image_settings() -> LLMSettings:
    """Load image LLM settings, falling back to the search model."""
    if not os.getenv("IMAGE_MODEL", "").strip():
        return get_search_settings()

    return _load_role_settings("IMAGE", default_temperature=0.1)


def get_youtube_settings() -> LLMSettings:
    """Load YouTube settings, falling back to the multimodal image model."""
    if not os.getenv("YOUTUBE_MODEL", "").strip():
        return get_image_settings()

    return _load_role_settings(
        "YOUTUBE",
        default_temperature=0.1,
        default_timeout=300,
    )


def get_duplicate_judge_settings() -> LLMSettings:
    """Load duplicate-judge settings, falling back to the router model."""
    if not os.getenv("DUPLICATE_JUDGE_MODEL", "").strip():
        return get_router_settings()

    return _load_role_settings(
        "DUPLICATE_JUDGE",
        default_temperature=0.0,
    )
