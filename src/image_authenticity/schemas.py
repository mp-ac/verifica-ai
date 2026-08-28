"""Structured results produced by image-authenticity analysis."""

from typing import Literal

from pydantic import BaseModel, Field


ImageAuthenticityAssessment = Literal[
    "likely_ai_generated",
    "likely_not_ai_generated",
    "inconclusive",
]


class ImageAuthenticityModelResult(BaseModel):
    """Probabilistic visual assessment returned by the configured model."""

    assessment: ImageAuthenticityAssessment = Field(
        description="Conclusão probabilística baseada apenas em sinais visuais"
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confiança estimada ou null quando não houver base suficiente",
    )
    signals: list[str] = Field(
        default_factory=list,
        description="Sinais visuais objetivos que sustentam a avaliação",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Fatores que limitam a confiabilidade da avaliação",
    )


class ImageAuthenticityAnalysis(ImageAuthenticityModelResult):
    """Assessment associated with one image in the request attachments."""

    attachment_index: int = Field(ge=0)
    status: Literal["completed", "unavailable"]
    method: Literal["visual_model"] = "visual_model"
