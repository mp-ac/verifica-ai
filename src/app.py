import os
from dotenv import load_dotenv

from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from tools import tools

load_dotenv()

model = ChatOpenAI(
    model=os.getenv("VLLM_MODEL", os.getenv("LOCAL_MODEL")),
    base_url=os.getenv("VLLM_BASE_URL", os.getenv("PROVIDER_URL")),
    api_key=os.getenv("VLLM_API_KEY", os.getenv("PROVIDER_API_KEY")),
    temperature=0.2,
    timeout=120,
)

model_with_tools = model.bind_tools(tools)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def call_model(state: AgentState):
    system_prompt_text = os.getenv("SYSTEM_PROMPT", "")
    prompt_file = os.getenv("SYSTEM_PROMPT_FILE")

    if prompt_file:
        with open(prompt_file, "r", encoding="utf-8") as f:
            system_prompt_text = f.read()

    system_prompt = {
        "role": "system",
        "content": system_prompt_text
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
