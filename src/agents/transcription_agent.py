from langchain.agents import create_agent

from config import TRANSCRIPTION_AGENT_PROMPT
from graph.state import AgentInput
from llm_registry import agent_llm
from tools.audio_transcription import audio_transcription
from utils.prompts_util import load_prompt

transcription_agent = create_agent(
    agent_llm,
    tools=[audio_transcription],
    system_prompt=load_prompt(TRANSCRIPTION_AGENT_PROMPT),
)


def _build_search_query(semantic_result: str) -> str:
    return "\n".join([
        "Analise a alegação extraída de uma transcrição de áudio.",
        "",
        semantic_result,
    ])


def query_transcription(state: AgentInput) -> dict:
    """Query the Transcription Agent."""
    result = transcription_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    semantic_result = result["messages"][-1].content

    return {
        "query": _build_search_query(semantic_result),
        "results": [
            {
                "source": "transcription_agent",
                "result": semantic_result,
            }
        ],
        "debug_events": [
            "Agente de transcrição concluiu a transcrição e extraiu o contexto semântico.",
        ],
    }
