import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

router_llm = ChatOpenAI(
    model=os.getenv("SMALL_VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("SMALL_VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("SMALL_VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.5,
    timeout=120,
)

agent_llm = ChatOpenAI(
    model=os.getenv("VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.1,
    timeout=120,
)
