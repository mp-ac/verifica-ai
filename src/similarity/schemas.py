from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DuplicateCandidate(BaseModel):
    """One semantic candidate retrieved from a previous analysis."""

    id: str = Field(min_length=1)
    match_type: Literal["semantic"] = "semantic"
    rank: int = Field(ge=1, le=3)
    score: float
    text: str = Field(min_length=1)


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
