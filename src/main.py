from graph.workflow import workflow


query = input("O que você quer procurar? ")

print("\n" + "=" * 80)
print("FASE 1 - MENSAGEM DO USUARIO")
print("=" * 80)
print(query)

for chunk in workflow.stream({"query": query}, stream_mode="updates"):
    for step, data in chunk.items():
        if step == "classify":
            print("\n" + "=" * 80)
            print("FASE 2 - ROUTER INTERPRETOU E CLASSIFICOU")
            print("=" * 80)
            for event in data.get("debug_events", []):
                print(f"- {event}")
            print("\nClassificacoes:")
            for classification in data.get("classifications", []):
                print(f"- {classification['source']}: {classification['query']}")

        elif step == "search_agent":
            print("\n" + "=" * 80)
            print("FASE 3 - AGENTE DE BUSCA EXECUTOU")
            print("=" * 80)
            for event in data.get("debug_events", []):
                print(f"- {event}")
            print("\nResultado bruto do agente:")
            for result in data.get("results", []):
                print(f"\n[{result['source']}]")
                print(result["result"])

        elif step == "synthesize":
            print("\n" + "=" * 80)
            print("FASE 4 - ROUTER GEROU A RESPOSTA FINAL")
            print("=" * 80)
            for event in data.get("debug_events", []):
                print(f"- {event}")
            print("\nResposta final:")
            print(data.get("final_answer", ""))
