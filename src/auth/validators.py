from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_admin_tokens
from .models import TokenResponse
from .repository import TokenRepository


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
admin_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="AdminBearer")


def get_token_repo() -> TokenRepository:
    return TokenRepository()


def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    repo: TokenRepository = Depends(get_token_repo),
) -> TokenResponse:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Token ausente")

    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Token inválido")

    token = repo.get_token_by_value(credentials.credentials)
    if token is None:
        raise HTTPException(status_code=401, detail="Token não autorizado")

    return token


def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(admin_bearer_scheme),
) -> None:
    admin_tokens = get_admin_tokens()
    if not admin_tokens:
        raise HTTPException(status_code=500, detail="Token admin não configurado")

    if credentials is None:
        raise HTTPException(status_code=401, detail="Token ausente")

    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Token inválido")

    if credentials.credentials not in admin_tokens:
        raise HTTPException(status_code=401, detail="Token não autorizado")
