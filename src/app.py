import json5
import requests
import os
from dotenv import load_dotenv

from datetime import datetime
from time import sleep, monotonic
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from typing import Annotated, TypedDict

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

import serpapi

from util import _extract_excerpt_from_markdown, _extract_title_from_markdown

load_dotenv()


@tool("current_date")
def current_date() -> str:
    """Retorna a data e hora atual no formato YYYY-MM-DD H:i:s"""
    tz = ZoneInfo("America/Rio_Branco")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


@tool('get_links')
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
                ensure_ascii=False
            )

        client = serpapi.Client(api_key=api_key)
        results = client.search({
            "q": query,
            "location": "Brazil",
            "hl": "pt",
            "gl": "br",
            "no_cache": "true",
            "api_key": api_key
        })

        organic = results.get("organic_results", [])

        if not organic:
            return json5.dumps(
                {
                    "query": query,
                    "total_results": 0,
                    "results": [],
                },
                ensure_ascii=False
            )

        formatted = []

        for position, r in enumerate(organic[:10], start=1):
            formatted.append({
                "position": position,
                "title": r.get("title", "Sem título"),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "source": "google",
            })

        return json5.dumps(
            {
                "query": query,
                "total_results": len(formatted),
                "results": formatted,
            },
            ensure_ascii=False
        )

    except Exception as e:
        return json5.dumps(
            {
                "erro": "Não foi possível realizar a busca na web.",
                "detalhes": str(e),
                "query": query,
            },
            ensure_ascii=False
        )


@tool("fetch_url")
def fetch_url(url: str) -> str:
    """Lê uma URL com o endpoint do Docling e retorna o conteúdo convertido para markdown.

    Use esta tool depois de `get_links` para abrir uma fonte específica e obter seu
    conteúdo principal em markdown limpo. A tool envia a URL para o endpoint do Docling,
    aguarda o processamento terminar e devolve o documento convertido junto dos metadados
    principais da execução.
    """

    base_url = os.getenv("DOCLING_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    bearer_token = os.getenv("DOCLING_BEARER_TOKEN")
    submit_url = os.getenv("DOCLING_SUBMIT_URL", f"{base_url}/document_to_markdown")
    status_url_template = os.getenv("DOCLING_STATUS_URL_TEMPLATE", f"{base_url}/status/{{task_id}}")
    timeout_seconds = float(os.getenv("DOCLING_TIMEOUT_SECONDS", "60"))
    poll_interval_seconds = float(os.getenv("DOCLING_POLL_INTERVAL_SECONDS", "1"))

    if not bearer_token:
        return json5.dumps(
            {
                "url": url,
                "erro": "A variável de ambiente DOCLING_BEARER_TOKEN não foi definida.",
            },
            ensure_ascii=False
        )

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    }

    payload = {
        "url": url,
        "include_full_text": "true",
    }

    try:
        submit_response = requests.post(
            submit_url,
            data=payload,
            headers=headers,
            timeout=30,
        )
        submit_response.raise_for_status()
        submit_data = submit_response.json()
    except requests.exceptions.RequestException as e:
        return json5.dumps(
            {
                "url": url,
                "erro": "Não foi possível enviar a URL para o Docling.",
                "detalhes": str(e),
            },
            ensure_ascii=False
        )
    except ValueError as e:
        return json5.dumps(
            {
                "url": url,
                "erro": "O endpoint do Docling retornou uma resposta inválida ao criar a tarefa.",
                "detalhes": str(e),
            },
            ensure_ascii=False
        )

    task_id = submit_data.get("task_id")
    if not task_id:
        return json5.dumps(
            {
                "url": url,
                "erro": "O endpoint do Docling não retornou task_id.",
                "resposta": submit_data,
            },
            ensure_ascii=False
        )

    started_at = monotonic()

    while monotonic() - started_at <= timeout_seconds:
        try:
            status_response = requests.get(
                status_url_template.format(task_id=task_id),
                headers=headers,
                timeout=30,
            )
            status_response.raise_for_status()
            status_data = status_response.json()
        except requests.exceptions.RequestException as e:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "erro": "Não foi possível consultar o status da tarefa no Docling.",
                    "detalhes": str(e),
                },
                ensure_ascii=False
            )
        except ValueError as e:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "erro": "O endpoint de status do Docling retornou uma resposta inválida.",
                    "detalhes": str(e),
                },
                ensure_ascii=False
            )

        status = status_data.get("status", "").lower()

        if status == "done":
            result = status_data.get("result", {})
            document = result.get("document", "")
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            title = _extract_title_from_markdown(document)
            excerpt = _extract_excerpt_from_markdown(document)

            return json5.dumps(
                {
                    "url": url,
                    "domain": domain,
                    "task_id": task_id,
                    "status": status_data.get("status"),
                    "elapsed_seconds": status_data.get("elapsed_seconds"),
                    "title": title,
                    "excerpt": excerpt,
                    "content_length": len(document),
                    "document": document,
                    "chunks": result.get("chunks", []),
                    "source_type": "docling",
                },
                ensure_ascii=False
            )

        if status in {"error", "failed", "cancelled"}:
            return json5.dumps(
                {
                    "url": url,
                    "task_id": task_id,
                    "status": status_data.get("status"),
                    "erro": "O Docling não conseguiu processar a URL.",
                    "detalhes": status_data,
                },
                ensure_ascii=False
            )

        sleep(poll_interval_seconds)

    return json5.dumps(
        {
            "url": url,
            "task_id": task_id,
            "erro": "Timeout aguardando o processamento da URL no Docling.",
            "timeout_seconds": timeout_seconds,
        },
        ensure_ascii=False
    )


tools = [current_date, get_links, fetch_url]

model = ChatOpenAI(
    model=os.getenv("VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.2,
    timeout=30,
)

model_with_tools = model.bind_tools(tools)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def call_model(state: AgentState):
    system_prompt = {
        "role": "system",
        "content": (
            "Você é um agente de pesquisa e apoio. Responda sempre em Português do Brasil. "
            "Você deve fazer buscas se uma informação é verdadeira ou falsa."
            "Use a ferramenta de get_links para buscar no Google e a fetch_url para acessar 3 links importantes"
            "Gere um relatório para o usuário, citando as fontes e um veredito se é Fake ou Verdadeiro"
        )
    }

    messages = [system_prompt] + state["messages"]
    response = model_with_tools.invoke(messages)

    return {"messages": [response]}


graph_builder = StateGraph(AgentState)

graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.add_edge(START, "agent")

graph_builder.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        END: END,
    }
)

graph_builder.add_edge("tools", "agent")
graph = graph_builder.compile()


while True:
    user_input = input("Enter your query: ")

    for chunk in graph.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            print(f"step: {step}")

            last_message = data["messages"][-1]

            if hasattr(last_message, "content_blocks"):
                print(f"content: {last_message.content_blocks}")
            else:
                print(f"content: {last_message.content}")

            print("-----")
