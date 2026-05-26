import os
from dotenv import load_dotenv
from typing import Annotated, Literal, TypedDict
import operator

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from tools.fetch_url import fetch_url
from tools.get_links import get_links

load_dotenv()

router_llm = ChatOpenAI(
    model=os.getenv("VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.2,
    timeout=120,
)

model = ChatOpenAI(
    model=os.getenv("VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.2,
    timeout=120,
)


class AgentInput(TypedDict):
    """Simple input state for each subagent."""
    query: str


class AgentOutput(TypedDict):
    """Output from each subagent."""
    source: str
    result: str


class Classification(TypedDict):
    """A single routing decision: which agent to call with what query."""
    source: Literal["search_agent", ]
    query: str


class RouterState(TypedDict):
    query: str
    classifications: list[Classification]
    results: Annotated[list[AgentOutput], operator.add]  # Reducer collects parallel results
    final_answer: str


search_agent = create_agent(
    model,
    tools=[get_links, fetch_url],
    system_prompt=(
        "Você é um especialista em buscar online se uma informação é FALSA ou VERDADEIRA"
        "Sempre use ferramentas que te auxiliem a buscar informações atualizadas "
        "para saber se alguma questão é VERDADEIRA ou FALSA"
    ),
)


# Define structured output schema for the classifier
class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""
    classifications: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
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
            "content": f"""Synthesize these search results to answer the original question: "{state['query']}"
            - Combine information from multiple sources without redundancy
            - Highlight the most relevant and actionable information
            - Note any discrepancies between sources
            - Keep the response concise and well-organized"""
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
    "query": "É verdade que a Pfizer listou infecção por hantavírus como efeito colateral de vacina contra Covid-19?"
})

print("Original query:", result["query"])
print("\nClassifications:")
for c in result["classifications"]:
    print(f"  {c['source']}: {c['query']}")
print("\n" + "=" * 60 + "\n")
print("Final Answer:")
print(result["final_answer"])
