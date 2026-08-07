from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from graph.state import Attachment, FinalAnswerResult


class RequesterInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    conversation_id: str | None = Field(default=None, max_length=255)
    message_id: str | None = Field(default=None, max_length=255)


class RequesterApplication(BaseModel):
    id: UUID
    name: str


class Requester(BaseModel):
    application: RequesterApplication
    external_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None


class AnalyzeRequest(BaseModel):
    query: str | None = Field(
        default=None,
        min_length=1,
        description="Consulta a ser analisada pelo workflow"
    )
    attachments: list[Attachment] = Field(
        default_factory=list,
        description="Conteúdos enviados pelo usuário para análise",
    )
    requester: RequesterInput | None = Field(
        default=None,
        description="Identificação externa de quem originou a solicitação",
    )

    @model_validator(mode="after")
    def validate_content(self) -> "AnalyzeRequest":
        if self.query is not None:
            self.query = self.query.strip()

        if not self.query and not self.attachments:
            raise ValueError("Informe uma query ou ao menos um attachment.")

        return self


class TokenUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    thinking_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ExecutionModel(BaseModel):
    role: Literal["router", "search", "image"]
    provider: str
    model: str
    usage: TokenUsage = Field(default_factory=TokenUsage)


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
    attachments: list[Attachment] = Field(default_factory=list)
    final_answer: FinalAnswerResult | None = None


class AnalyzeEnqueueResponse(BaseModel):
    task_id: str
    status: str


class AnalyzeStatusResponse(BaseModel):
    status: str
    result: AnalyzeResponse | None = None
    execution: ExecutionMetadata | None = None
    error: str | None = None
