import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field


class AgentInput(TypedDict):
    """Simple input state for each subagent."""
    query: str


class AgentOutput(TypedDict):
    """Output from each subagent."""
    source: str
    result: str


class Classification(TypedDict):
    """A single routing decision: which agent to call with what query."""
    source: Literal["search_agent", "transcription_agent"]
    query: str


class SourceItem(BaseModel):
    title: str
    url: str


class FinalAnswerResult(BaseModel):
    answer: str = Field(description="Resposta final consolidada para o usuário")
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Fontes que foram usadas pelos agentes"
    )


class RouterState(TypedDict):
    query: str
    classifications: list[Classification]
    results: Annotated[list[AgentOutput], operator.add]
    debug_events: Annotated[list[str], operator.add]
    final_answer: FinalAnswerResult


class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""
    classifications: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
    )
