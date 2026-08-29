import operator
from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator

from image_authenticity import ImageAuthenticityAnalysis


AttachmentType = Literal[
    "image",
    "video",
    "audio",
    "youtube",
    "web",
    "unknown",
]
AttachmentOrigin = Literal["payload", "query"]
ClassificationLabel = Literal[
    "verdadeiro",
    "falso",
    "enganoso",
    "inconclusivo",
]


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
    attachment_index: NotRequired[int]


class AgentOutput(TypedDict):
    """Output from each subagent."""
    source: str
    result: str


class ModelUsage(TypedDict):
    """Token usage produced by one or more calls to a model role."""
    role: Literal["router", "search", "image", "youtube"]
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cached_input_tokens: int
    total_tokens: int


class Classification(TypedDict):
    """A single routing decision: which agent to call with what query."""
    source: Literal[
        "search_agent",
        "transcription_agent",
        "image_agent",
        "image_authenticity_agent",
        "youtube_agent",
    ]
    query: str
    attachment: NotRequired[dict]
    attachment_index: NotRequired[int]


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
    title: str = Field(
        default="",
        description=(
            "Núcleo curto e objetivo do título, sem prefixo de classificação"
        ),
    )
    answer: str = Field(description="Resposta final consolidada para o usuário")
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Fontes que foram usadas pelos agentes"
    )
    classification: ClassificationLabel | None = Field(
        default=None,
        description=(
            "Veredito geral da análise. Use null quando não houver uma "
            "alegação factual classificável."
        ),
    )
    is_classified: bool = Field(
        default=False,
        description="Indica se a análise recebeu um veredito geral.",
    )

    @model_validator(mode="after")
    def derive_classification_status(self) -> "FinalAnswerResult":
        """Keep the boolean consistent with the structured verdict."""
        self.is_classified = self.classification is not None
        return self


class RouterState(TypedDict):
    query: str
    research_query: str
    attachments: list[dict]
    classifications: list[Classification]
    media_contexts: Annotated[list[AgentOutput], operator.add]
    image_factual_claims_detected: Annotated[list[bool], operator.add]
    image_authenticity_analyses: Annotated[
        list[ImageAuthenticityAnalysis],
        operator.add,
    ]
    youtube_central_claim: NotRequired[str]
    youtube_research_context: NotRequired[str]
    youtube_requires_clarification: NotRequired[bool]
    youtube_clarification_reason: NotRequired[str]
    results: Annotated[list[AgentOutput], operator.add]
    sources: Annotated[list[SourceItem], operator.add]
    tools: Annotated[list[str], operator.add]
    model_usage: Annotated[list[ModelUsage], operator.add]
    debug_events: Annotated[list[str], operator.add]
    human_response_required: NotRequired[bool]
    final_answer: FinalAnswerResult


class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""
    classifications: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
    )
