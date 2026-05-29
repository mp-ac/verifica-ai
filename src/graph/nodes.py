from llms import router_llm
from langgraph.types import Send
from graph.state import ClassificationResult, RouterState
from util import load_prompt


def classify_query(state: RouterState) -> dict:
    """Classify query and determine which agents to invoke."""
    structured_llm = router_llm.with_structured_output(ClassificationResult)

    result = structured_llm.invoke([
        {
            "role": "system",
            "content": load_prompt("prompts/router_classification_prompt.md")

        },
        {"role": "user", "content": state["query"]}
    ])

    return {"classifications": result.classifications}


def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    return [
        Send(c["source"], {"query": c["query"]})
        for c in state["classifications"]
    ]


def synthesize_results(state: RouterState) -> dict:
    """Combine results from all agents into a coherent answer."""
    if not state["results"]:
        return {"final_answer": "No results found from any knowledge source."}

    formatted = [
        f"**From {r['source'].title()}:**\n{r['result']}"
        for r in state["results"]
    ]

    synthesis_response = router_llm.invoke([
        {
            "role": "system",
            "content": f"""Gere a resposta final para a pergunta original: "{state['query']}"
            Use exclusivamente os resultados fornecidos pelos agentes.
            Não realize nova apuração.
            Não acrescente fatos, fontes, links ou conclusões que não estejam nos resultados recebidos.
            Se os resultados dos agentes forem insuficientes, indique essa limitação claramente.
            Combine as informações sem redundância, preservando evidências,
            fontes e limitações apresentadas pelos agentes."""
        },
        {"role": "user", "content": "\n\n".join(formatted)}
    ])

    return {"final_answer": synthesis_response.content}
