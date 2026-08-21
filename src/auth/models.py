from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class TokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    token: Optional[str] = Field(default=None, min_length=3, max_length=255)
    active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("name não pode ser vazio.")
        return name


class TokenUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name:
            raise ValueError("name não pode ser vazio.")
        return name

    @model_validator(mode="after")
    def validate_update(self) -> "TokenUpdateRequest":
        if self.name is None and self.active is None:
            raise ValueError("Informe name ou active.")
        return self


class TokenResponse(BaseModel):
    id: int
    application_id: UUID
    name: str
    token_preview: Optional[str] = Field(
        default=None,
        description="Prévia mascarada do token (primeiros e últimos 4 caracteres).",
    )
    active: bool
    created_at: datetime


class TokenCreateResponse(TokenResponse):
    """Returned only on POST /admin/tokens — includes the plaintext token."""
    token: Optional[str] = Field(
        default=None,
        description=(
            "Token em texto claro. Retornado somente na criação (POST). "
            "Nas demais operações o campo é omitido."
        ),
    )


class TokenListResponse(BaseModel):
    items: List[TokenResponse]
    limit: int
    offset: int
