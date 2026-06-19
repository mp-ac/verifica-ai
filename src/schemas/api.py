from pydantic import BaseModel, Field

from graph.state import FinalAnswerResult


class AnalyzeRequest(BaseModel):
    query: str = Field(
        min_length=1,
        description="Consulta a ser analisada pelo workflow"
    )


class AnalyzeResponse(BaseModel):
    query: str
    final_answer: FinalAnswerResult | None = None
