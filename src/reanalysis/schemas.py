"""Contracts used by the reanalysis flow."""

from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from graph.state import (
    Attachment,
    ClassificationLabel,
    FinalAnswerResult,
    SourceItem,
)
from image_authenticity import ImageAuthenticityAnalysis
from schemas.api import ExecutionMetadata


class ReanalyzeRequest(BaseModel):
    reanalysis_id: UUID
    final_result_id: UUID
    prompt: str = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def normalize_prompt(self) -> "ReanalyzeRequest":
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("Informe uma instrução para a reanálise.")

        return self


class PanelFinalResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    query: str
    title: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    final_result: str
    classification: ClassificationLabel | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    has_human_review: bool = Field(
        validation_alias="is_classified",
        serialization_alias="is_classified",
    )

    @field_validator("attachments", "sources", mode="before")
    @classmethod
    def normalize_nullable_lists(cls, value: list | None) -> list:
        return value or []

    def to_final_answer(self) -> FinalAnswerResult:
        return FinalAnswerResult(
            title=self.title or "",
            answer=self.final_result,
            classification=self.classification,
            sources=self.sources,
        )


class PanelFinalResultResponse(BaseModel):
    data: PanelFinalResult


class ReanalyzeEnqueueResponse(BaseModel):
    task_id: str
    status: Literal["queued"] = "queued"


class ReanalysisResponse(BaseModel):
    reanalysis_id: UUID
    final_result_id: UUID
    prompt: str
    final_answer: FinalAnswerResult
    image_authenticity_analyses: list[ImageAuthenticityAnalysis] = Field(
        default_factory=list
    )


class ReanalysisStatusResponse(BaseModel):
    status: str
    result: ReanalysisResponse | None = None
    execution: ExecutionMetadata | None = None
    error: str | None = None
