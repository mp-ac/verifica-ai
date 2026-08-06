from langchain.agents import create_agent
from langchain_core.messages import ToolMessage

from config import TRANSCRIPTION_AGENT_PROMPT
from graph.state import AgentInput, Attachment
from llm_registry import agent_llm
from tools.audio_transcription import audio_transcription
from utils.prompts_util import load_prompt
from utils.token_usage import get_token_usage

transcription_agent = create_agent(
    agent_llm,
    tools=[audio_transcription],
    system_prompt=load_prompt(TRANSCRIPTION_AGENT_PROMPT),
)


def _get_used_tools(agent_messages: list) -> list[str]:
    """
    Retorna os nomes únicos e ordenados das ferramentas executadas.
    """
    return sorted({
        message.name
        for message in agent_messages
        if isinstance(message, ToolMessage) and message.name
    })


def query_transcription(state: AgentInput) -> dict:
    """Query the Transcription Agent."""
    attachment = Attachment.model_validate(state.get("attachment"))
    if attachment.type not in {"audio", "video"}:
        raise ValueError("O agente de transcrição recebeu um attachment inválido.")

    result = transcription_agent.invoke({
        "messages": [{"role": "user", "content": str(attachment.url)}]
    })
    return {
        "media_contexts": [
            {
                "source": "transcription_agent",
                "result": result["messages"][-1].content,
            }
        ],
        "tools": _get_used_tools(result["messages"]),
        "model_usage": [{
            "role": "search",
            **get_token_usage(result["messages"]),
        }],
        "debug_events": ["Agente de transcrição concluiu a transcrição."],
    }
