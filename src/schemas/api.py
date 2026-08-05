from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from graph.state import FinalAnswerResult


class AnalyzeRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Consulta a ser analisada pelo workflow"
    )


class ExecutionModel(BaseModel):
    role: Literal["router", "search", "image"]
    provider: str
    model: str


class ExecutionMetadata(BaseModel):
    models: list[ExecutionModel] = Field(default_factory=list)
    agents: list[
        Literal["search_agent", "transcription_agent", "image_agent"]
    ] = Field(
        default_factory=list
    )
    tools: list[str] = Field(default_factory=list)
    duration_ms: int | None = Field(default=None, ge=0)
    completed_at: datetime | None = None
    app_version: str | None = None


class AnalyzeResponse(BaseModel):
    query: str
    final_answer: FinalAnswerResult | None = None


class AnalyzeEnqueueResponse(BaseModel):
    task_id: str
    status: str


class AnalyzeStatusResponse(BaseModel):
    status: str
    result: AnalyzeResponse | None = None
    execution: ExecutionMetadata | None = None
    error: str | None = None
