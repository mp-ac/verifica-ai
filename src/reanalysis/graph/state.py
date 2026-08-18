"""LangGraph state for reanalysis."""

import operator
from typing import Annotated, NotRequired, TypedDict

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
    youtube_central_claim: NotRequired[str]
    youtube_research_context: NotRequired[str]
    youtube_requires_clarification: NotRequired[bool]
    youtube_clarification_reason: NotRequired[str]
    results: Annotated[list[AgentOutput], operator.add]
    sources: Annotated[list[SourceItem], operator.add]
    tools: Annotated[list[str], operator.add]
    model_usage: Annotated[list[ModelUsage], operator.add]
    debug_events: Annotated[list[str], operator.add]
    final_answer: FinalAnswerResult
