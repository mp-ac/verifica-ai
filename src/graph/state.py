import operator
from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import AnyHttpUrl, BaseModel, Field, model_validator


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
        "youtube_agent",
    ]
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


class YouTubeRelevantSegment(BaseModel):
    """A video segment that is directly relevant to the central claim."""
    timestamp: str = Field(description="Timestamp inicial no formato MM:SS ou HH:MM:SS")
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
                raise ValueError(
                    "O motivo do esclarecimento é obrigatório."
                )
            return self

        if not self.central_claim or self.central_claim_source is None:
            raise ValueError(
                "A análise deve definir uma alegação central e sua origem."
            )
        return self


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
    youtube_central_claim: NotRequired[str]
    youtube_requires_clarification: NotRequired[bool]
    youtube_clarification_reason: NotRequired[str]
    results: Annotated[list[AgentOutput], operator.add]
    sources: Annotated[list[SourceItem], operator.add]
    tools: Annotated[list[str], operator.add]
    model_usage: Annotated[list[ModelUsage], operator.add]
    debug_events: Annotated[list[str], operator.add]
    final_answer: FinalAnswerResult


class ClassificationResult(BaseModel):
    """Result of classifying a user query into agent-specific sub-questions."""
    classifications: list[Classification] = Field(
        description="List of agents to invoke with their targeted sub-questions"
    )
