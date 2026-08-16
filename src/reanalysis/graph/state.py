"""LangGraph state for reanalysis."""

import operator
from typing import Annotated, TypedDict

from graph.state import (
    AgentOutput,
    Attachment,
    FinalAnswerResult,
    ModelUsage,
    SourceItem,
)


class ReanalysisState(TypedDict):
    query: str
    prompt: str
    attachments: list[Attachment]
    original_final_answer: FinalAnswerResult
    media_contexts: Annotated[list[AgentOutput], operator.add]
    results: Annotated[list[AgentOutput], operator.add]
    sources: Annotated[list[SourceItem], operator.add]
    tools: Annotated[list[str], operator.add]
    model_usage: Annotated[list[ModelUsage], operator.add]
    debug_events: Annotated[list[str], operator.add]
    final_answer: FinalAnswerResult
