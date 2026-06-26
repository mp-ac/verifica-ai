from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from llm_settings import LLMSettings


def build_llm(settings: LLMSettings):
    """Build a LangChain chat model from provider-specific settings."""
    if settings.provider in {"openai", "vllm"}:
        return ChatOpenAI(
            model=settings.model,
            base_url=settings.base_url,
            api_key=settings.api_key,
            temperature=settings.temperature,
            timeout=settings.timeout,
        )

    if settings.provider == "google":
        return ChatGoogleGenerativeAI(
            model=settings.model,
            google_api_key=settings.api_key,
            temperature=settings.temperature,
            timeout=settings.timeout,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.provider}")
