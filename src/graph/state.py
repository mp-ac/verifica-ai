import operator
from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import AnyHttpUrl, BaseModel, Field


AttachmentType = Literal["image", "video", "audio", "web", "unknown"]
AttachmentOrigin = Literal["payload", "query"]


class Attachment(BaseModel):
    """Content supplied by the user for analysis."""
    type: AttachmentType = "unknown"
    url: AnyHttpUrl
    mime_type: str | None = None
    origin: AttachmentOrigin = "payload"


class AgentInput(TypedDict):
    """Simple input state for each subagent."""
    query: str
    research_query: NotRequired[str]
    attachment: NotRequired[dict]


class AgentOutput(TypedDict):
    """Output from each subagent."""
    source: str
    result: str


class ModelUsage(TypedDict):
    """Token usage produced by one or more calls to a model role."""
    role: Literal["router", "search", "image"]
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cached_input_tokens: int
    total_tokens: int


class Classification(TypedDict):
    """A single routing decision: which agent to call with what query."""
    source: Literal["search_agent", "transcription_agent", "image_agent"]
    query: str
    attachment: NotRequired[dict]


class ImageAnalysisResult(BaseModel):
    """Structured information extracted from an image for online research."""
    visible_text: str = Field(
        description="Texto relevante visível na imagem"
    )
    visual_context: str = Field(
        description="Descrição objetiva do contexto visual relevante"
    )
    claims: list[str] = Field(
        default_factory=list,
        description="Alegações factuais identificadas na imagem",
    )
    research_query: str = Field(
        description="Consulta textual recomendada para pesquisa online"
    )


class SourceItem(BaseModel):
    title: str
    url: str


class FinalAnswerResult(BaseModel):
    answer: str = Field(description="Resposta final consolidada para o usuário")
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Fontes que foram usadas pelos agentes"
    )


class RouterState(TypedDict):
    query: str
    research_query: str
    attachments: list[dict]
    classifications: list[Classification]
    media_contexts: Annotated[list[AgentOutput], operator.add]
    results: Annotated[list[AgentOutput], operator.add]
    tools: Annotated[list[str], operator.add]
    model_usage: Annotated[list[ModelUsage], operator.add]
    debug_events: Annotated[list[str], operator.add]
    final_answer: FinalAnswerResult


class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""
    classifications: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
    )
