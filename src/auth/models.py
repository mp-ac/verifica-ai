from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenCreateRequest(BaseModel):
    token: Optional[str] = Field(default=None, min_length=3, max_length=255)
    active: bool = True


class TokenUpdateRequest(BaseModel):
    active: bool


class TokenResponse(BaseModel):
    id: int
    token: str
    active: bool
    created_at: datetime


class TokenListResponse(BaseModel):
    items: List[TokenResponse]
    limit: int
    offset: int
