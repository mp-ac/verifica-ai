import os

import json5
import serpapi
from langchain_core.tools import tool


@tool("get_links")
def get_links(query: str):
    """
    Busca resultados iniciais na web e retorna fontes candidatas para leitura posterior.

    Use esta tool para descobrir links potencialmente relevantes para a pergunta do usuário.
    Ela não acessa o conteúdo completo das páginas; apenas retorna metadados básicos dos
    resultados encontrados para que o agente decida quais URLs deve abrir depois.
    """

    try:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return json5.dumps(
                {"erro": "A variável de ambiente SERPAPI_API_KEY não foi definida."},
                ensure_ascii=False,
            )

        client = serpapi.Client(api_key=api_key)
        results = client.search(
            {
                "q": query,
                "location": "Brazil",
                "hl": "pt",
                "gl": "br",
                "no_cache": "true",
                "api_key": api_key,
            }
        )

        organic = results.get("organic_results", [])

        if not organic:
            return json5.dumps(
                {
                    "query": query,
                    "total_results": 0,
                    "results": [],
                },
                ensure_ascii=False,
            )

        formatted = []

        for position, result in enumerate(organic[:10], start=1):
            formatted.append(
                {
                    "position": position,
                    "title": result.get("title", "Sem título"),
                    "url": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "source": "google",
                }
            )

        return json5.dumps(
            {
                "query": query,
                "total_results": len(formatted),
                "results": formatted,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        return json5.dumps(
            {
                "erro": "Não foi possível realizar a busca na web.",
                "detalhes": str(e),
                "query": query,
            },
            ensure_ascii=False,
        )
