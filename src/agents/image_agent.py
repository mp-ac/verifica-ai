import re

from langchain_core.messages import HumanMessage

from config import IMAGE_AGENT_PROMPT
from graph.state import AgentInput, ImageAnalysisResult
from llm_registry import image_llm
from utils.prompts_util import load_prompt


def _extract_image_url(query: str) -> str:
    """Extract the first public HTTP(S) URL from the routed query."""
    match = re.search(r'https?://[^\s<>"\']+', query)
    if match is None:
        raise ValueError("Nenhuma URL de imagem foi encontrada na consulta.")

    return match.group(0).rstrip(".,;:!?)]}")


def _format_analysis(analysis: ImageAnalysisResult) -> str:
    """Format the visual analysis as research context for the search agent."""
    claims = "\n".join(f"- {claim}" for claim in analysis.claims)
    if not claims:
        claims = "- Nenhuma alegação factual explícita foi identificada."

    return (
        f"Texto visível na imagem:\n{analysis.visible_text}\n\n"
        f"Contexto visual:\n{analysis.visual_context}\n\n"
        f"Alegações identificadas:\n{claims}\n\n"
        f"Consulta sugerida para pesquisa:\n{analysis.research_query}"
    )


def query_image(state: AgentInput) -> dict:
    """Analyze an image and prepare its factual claims for online research."""
    image_url = _extract_image_url(state["query"])
    structured_llm = image_llm.with_structured_output(ImageAnalysisResult)
    analysis = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt(IMAGE_AGENT_PROMPT),
        },
        HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Analise esta imagem e prepare as alegações que devem "
                        "ser verificadas por um agente de pesquisa."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
            ]
        ),
    ])
    formatted_analysis = _format_analysis(analysis)

    return {
        "query": formatted_analysis,
        "results": [
            {
                "source": "image_agent",
                "result": formatted_analysis,
            }
        ],
        "debug_events": [
            "Agente de imagem analisou o conteúdo visual e preparou a pesquisa."
        ],
    }
