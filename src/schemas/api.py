from typing import Literal

from pydantic import BaseModel, Field

from graph.state import FinalAnswerResult


class AnalyzeRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Consulta a ser analisada pelo workflow"
    )


class ExecutionModel(BaseModel):
    role: Literal["router", "search"]
    provider: str
    model: str


class ExecutionMetadata(BaseModel):
    models: list[ExecutionModel] = Field(default_factory=list)
    agents: list[Literal["search_agent", "transcription_agent"]] = Field(
        default_factory=list
    )


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
