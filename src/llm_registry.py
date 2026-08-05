from llm_factory import build_llm
from llm_settings import get_image_settings, get_router_settings, get_search_settings


router_llm = build_llm(get_router_settings())

agent_llm = build_llm(get_search_settings())

image_llm = build_llm(get_image_settings())
