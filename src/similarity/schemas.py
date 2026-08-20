from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DuplicateCandidate(BaseModel):
    """One semantic candidate retrieved from a previous analysis."""

    id: str = Field(min_length=1)
    match_type: Literal["semantic"] = "semantic"
    rank: int = Field(ge=1, le=3)
    score: float
    text: str = Field(min_length=1)


class RetrievedCandidate(BaseModel):
    """One validated candidate returned by the semantic retriever API."""

    id: str = Field(min_length=1)
    match_type: Literal["exact_url", "semantic"]
    rank: int = Field(ge=1, le=3)
    score: float | None = None
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_semantic_score(self) -> "RetrievedCandidate":
        """Require a score for semantic candidates only."""
        if self.match_type == "semantic" and self.score is None:
            raise ValueError("Um candidato semântico deve informar score.")
        return self


class DuplicateAnalysisDecision(BaseModel):
    """Structured decision about whether a previous analysis is equivalent."""

    decision: Literal["match", "no_match", "uncertain"]
    candidate_id: str | None = None
    confidence: Literal["high", "medium", "low"]
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate_id(self) -> "DuplicateAnalysisDecision":
        """Require a candidate only when the decision refers to one."""
        if self.decision == "match" and self.candidate_id is None:
            raise ValueError("Uma correspondência deve informar candidate_id.")

        if self.decision == "no_match" and self.candidate_id is not None:
            raise ValueError("no_match não pode informar candidate_id.")

        return self


class DuplicateAnalysisJudgeResult(BaseModel):
    """Duplicate evaluation together with the model token usage."""

    evaluation: DuplicateAnalysisDecision
    model_usage: dict[str, int]


class DuplicateCheckResult(BaseModel):
    """Outcome of duplicate retrieval and optional LLM evaluation."""

    outcome: Literal[
        "skipped",
        "exact_match",
        "match",
        "no_match",
        "uncertain",
        "unavailable",
    ]
    candidate_id: str | None = None
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    evaluation: DuplicateAnalysisDecision | None = None
    model_usage: dict[str, int] = Field(default_factory=dict)
    failure_stage: Literal["retriever", "judge"] | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "DuplicateCheckResult":
        """Keep selected candidates and failure stages consistent."""
        if self.outcome in {"exact_match", "match"} and self.candidate_id is None:
            raise ValueError("Uma correspondência deve informar candidate_id.")
        if self.outcome == "unavailable" and self.failure_stage is None:
            raise ValueError("Um resultado indisponível deve informar a etapa.")
        if self.outcome != "unavailable" and self.failure_stage is not None:
            raise ValueError("Somente indisponibilidade pode informar a etapa.")
        return self
