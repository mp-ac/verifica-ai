from llm_factory import build_llm
from llm_settings import (
    get_duplicate_judge_settings,
    get_image_settings,
    get_router_settings,
    get_search_settings,
    get_youtube_settings,
)


router_llm = build_llm(get_router_settings())

agent_llm = build_llm(get_search_settings())

image_llm = build_llm(get_image_settings())

youtube_llm = build_llm(get_youtube_settings())

duplicate_judge_llm = build_llm(get_duplicate_judge_settings())
