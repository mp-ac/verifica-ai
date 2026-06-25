from langchain.agents import create_agent

from config import TRANSCRIPTION_AGENT_PROMPT
from graph.state import AgentInput
from llms import agent_llm
from tools.audio_transcription import audio_transcription
from utils.prompts_util import load_prompt

transcription_agent = create_agent(
    agent_llm,
    tools=[audio_transcription],
    system_prompt=load_prompt(TRANSCRIPTION_AGENT_PROMPT),
)


def query_transcription(state: AgentInput) -> dict:
    """Query the Transcription Agent."""
    result = transcription_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    return {
        "query": result["messages"][-1].content,
        "results": [
            {
                "source": "transcription_agent",
                "result": result["messages"][-1].content,
            }
        ],
        "debug_events": ["Agente de transcrição concluiu a transcrição."],
    }
