from langchain.agents import create_agent

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from graph.state import (
    AgentInput,
    ClassificationResult,
    RouterState,
)
from util import load_system_prompt
from llms import agent_llm, router_llm
from tools.current_date import current_date
from tools.fetch_url import fetch_url
from tools.get_links import get_links


search_agent = create_agent(
    agent_llm,
    tools=[current_date, get_links, fetch_url],
    system_prompt=load_system_prompt(),
)


def classify_query(state: RouterState) -> dict:
    """Classify query and determine which agents to invoke."""
    structured_llm = router_llm.with_structured_output(ClassificationResult)

    result = structured_llm.invoke([
        {
            "role": "system",
            "content": """Analyze this query and determine which knowledge bases to consult.
            For each relevant source, generate a targeted sub-question optimized for that source.
            Available sources:
            - search_agent : Search online about some information if it is TRUE or FALSE
            Return ONLY the sources that are relevant to the query. Each source should have
            a targeted sub-question optimized for that specific knowledge domain."""

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


def query_search(state: AgentInput) -> dict:
    """Query the Search Agent."""
    result = search_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    return {"results": [{"source": "search_agent", "result": result["messages"][-1].content}]}


def synthesize_results(state: RouterState) -> dict:
    """Combine results from all agents into a coherent answer."""
    if not state["results"]:
        return {"final_answer": "No results found from any knowledge source."}

    # Format results for synthesis
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
Combine as informações sem redundância, preservando evidências, fontes e limitações apresentadas pelos agentes."""
        },
        {"role": "user", "content": "\n\n".join(formatted)}
    ])

    return {"final_answer": synthesis_response.content}


workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("search_agent", query_search)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route_to_agents, ["search_agent",])
    .add_edge("search_agent", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)

result = workflow.invoke({
    "query": input("O que você quer procurar? ")
})

print("\n\n" + "-" * 80 + "\n\n")

print("Original query:", result["query"])
print("\nClassifications:")
for c in result["classifications"]:
    print(f"  {c['source']}: {c['query']}")
print("\n" + "=" * 60 + "\n")
print("Agent Results:")
for r in result["results"]:
    print(f"\nSource: {r['source']}")
    print("Result:")
    print(r["result"])
print("\n" + "=" * 60 + "\n")
print("Final Answer:")
print(result["final_answer"])
