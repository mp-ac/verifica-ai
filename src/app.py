from langgraph.graph import StateGraph, START, END

from agents.search_agent import query_search
from graph.nodes import classify_query, route_to_agents, synthesize_results
from graph.state import RouterState


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
