from typing import Literal

from pydantic import BaseModel, Field, model_validator


class YouTubeRelevantSegment(BaseModel):
    """A video segment that is directly relevant to the central claim."""

    timestamp: str = Field(
        description="Timestamp inicial no formato MM:SS ou HH:MM:SS"
    )
    spoken_excerpt: str | None = Field(
        default=None,
        description="Trecho falado diretamente relacionado à alegação central",
    )
    visual_context: str | None = Field(
        default=None,
        description="Contexto visual diretamente relacionado à alegação central",
    )
    relevance: str = Field(
        description="Por que o segmento ajuda a compreender a alegação central",
    )


class YouTubeAnalysisResult(BaseModel):
    """One focused factual-analysis target extracted from a YouTube video."""

    thumbnail_context: str | None = Field(
        default=None,
        description=(
            "Alegação ou contexto comunicado pela thumbnail, somente quando "
            "for relevante para compreender o foco"
        ),
    )
    central_claim: str | None = Field(
        default=None,
        description="A única alegação factual que deve ser pesquisada",
    )
    central_claim_source: Literal[
        "user_query",
        "video_title",
        "thumbnail",
    ] | None = Field(
        default=None,
        description="Origem usada para definir a alegação central",
    )
    relevant_segments: list[YouTubeRelevantSegment] = Field(
        default_factory=list,
        description="Somente os trechos relacionados à alegação central",
    )
    requires_clarification: bool = Field(
        default=False,
        description="Indica que o usuário precisa informar o foco da análise",
    )
    clarification_reason: str | None = Field(
        default=None,
        description="Motivo objetivo pelo qual não há foco único seguro",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Limitações encontradas durante a análise do vídeo",
    )

    @model_validator(mode="after")
    def validate_central_claim(self) -> "YouTubeAnalysisResult":
        """Require exactly one research target or an explicit clarification."""
        if self.requires_clarification:
            if self.central_claim is not None or self.central_claim_source is not None:
                raise ValueError(
                    "Uma análise que requer esclarecimento não pode definir "
                    "uma alegação central."
                )
            if not self.clarification_reason:
                raise ValueError("O motivo do esclarecimento é obrigatório.")
            return self

        if not self.central_claim or self.central_claim_source is None:
            raise ValueError(
                "A análise deve definir uma alegação central e sua origem."
            )
        return self
