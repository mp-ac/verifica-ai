import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query

from auth import (
    TokenCreateRequest,
    TokenListResponse,
    TokenRepository,
    TokenResponse,
    TokenUpdateRequest,
    build_auth_config_from_env,
    configure_auth,
    get_token_repo,
    init_auth_db,
    verify_admin_token,
    verify_bearer_token,
)
from graph.workflow import workflow
from schemas import AnalyzeRequest, AnalyzeResponse

load_dotenv()
configure_auth(build_auth_config_from_env())

enable_docs = os.getenv("DOCS_URL_ENABLED", "false").lower() == "true"
show_admin_docs = os.getenv("ADMIN_DOCS_ENABLED", "false").lower() == "true"

app = FastAPI(
    title=os.getenv("APP_NAME"),
    version=os.getenv("APP_VERSION"),
    docs_url="/docs" if enable_docs else None,
)


@app.on_event("startup")
async def startup() -> None:
    init_auth_db()


@app.get("/")
async def index() -> dict:
    return {
        "status": "success",
        "message": "DenuncIAI API",
    }


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    _token_data: TokenResponse = Depends(verify_bearer_token),
) -> AnalyzeResponse:
    try:
        final_answer = None

        for chunk in workflow.stream(
            {"query": payload.query},
            stream_mode="updates",
        ):
            for step, data in chunk.items():
                answer = data.get("final_answer")
                if answer is not None:
                    final_answer = answer

        return AnalyzeResponse(query=payload.query, final_answer=final_answer)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Falha ao executar o workflow de analise.",
        ) from exc


@app.get(
    "/admin/tokens",
    response_model=TokenListResponse,
    include_in_schema=show_admin_docs,
)
async def list_tokens(
    _auth: None = Depends(verify_admin_token),
    repo: TokenRepository = Depends(get_token_repo),
    active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TokenListResponse:
    items = repo.list_tokens(active=active, limit=limit, offset=offset)
    return TokenListResponse(items=items, limit=limit, offset=offset)


@app.post(
    "/admin/tokens",
    response_model=TokenResponse,
    status_code=201,
    include_in_schema=show_admin_docs,
)
async def create_token(
    payload: TokenCreateRequest,
    _auth: None = Depends(verify_admin_token),
    repo: TokenRepository = Depends(get_token_repo),
) -> TokenResponse:
    import uuid

    token = (payload.token or uuid.uuid4().hex).strip()
    if not token:
        raise HTTPException(status_code=422, detail="Token inválido")

    return repo.create_token(token=token, active=payload.active)


@app.patch(
    "/admin/tokens/{token_id}",
    response_model=TokenResponse,
    include_in_schema=show_admin_docs,
)
async def update_token(
    token_id: int,
    payload: TokenUpdateRequest,
    _auth: None = Depends(verify_admin_token),
    repo: TokenRepository = Depends(get_token_repo),
) -> TokenResponse:
    return repo.set_active(token_id=token_id, active=payload.active)


@app.delete(
    "/admin/tokens/{token_id}",
    status_code=204,
    include_in_schema=show_admin_docs,
)
async def delete_token(
    token_id: int,
    _auth: None = Depends(verify_admin_token),
    repo: TokenRepository = Depends(get_token_repo),
) -> None:
    repo.delete_token(token_id=token_id)
