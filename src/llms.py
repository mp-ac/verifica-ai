from langchain_openai import ChatOpenAI

from config import (
    ROUTER_API_KEY,
    ROUTER_BASE_URL,
    ROUTER_MODEL,
    SEARCH_API_KEY,
    SEARCH_BASE_URL,
    SEARCH_MODEL,
)

router_llm = ChatOpenAI(
    model=ROUTER_MODEL,
    base_url=ROUTER_BASE_URL,
    api_key=ROUTER_API_KEY,
    temperature=0.5,
    timeout=120,
)

agent_llm = ChatOpenAI(
    model=SEARCH_MODEL,
    base_url=SEARCH_BASE_URL,
    api_key=SEARCH_API_KEY,
    temperature=0.1,
    timeout=120,
)
