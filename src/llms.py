import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

router_llm = ChatOpenAI(
    model=os.getenv("ROUTER_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("ROUTER_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("ROUTER_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.5,
    timeout=120,
)

agent_llm = ChatOpenAI(
    model=os.getenv("SEARCH_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("SEARCH_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("SEARCH_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.1,
    timeout=120,
)
