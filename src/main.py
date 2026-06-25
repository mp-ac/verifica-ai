import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from redis import Redis
from rq import Queue
from rq.job import Job

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
from queueing import (
    failure_ttl_seconds,
    job_timeout_seconds,
    queue_name,
    redis_url,
    result_ttl_seconds,
)
from jobs import process_analyze_job
from schemas import (
    AnalyzeEnqueueResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStatusResponse,
)
from utils.job_utils import resolve_job_id

load_dotenv()
configure_auth(build_auth_config_from_env())

enable_docs = os.getenv("DOCS_URL_ENABLED", "false").lower() == "true"
show_admin_docs = os.getenv("ADMIN_DOCS_ENABLED", "false").lower() == "true"

app = FastAPI(
    title=os.getenv("APP_NAME"),
    version=os.getenv("APP_VERSION"),
    docs_url="/docs" if enable_docs else None,
)

redis_conn = Redis.from_url(redis_url())
q = Queue(queue_name(), connection=redis_conn)


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


@app.post("/analyze", response_model=AnalyzeEnqueueResponse, status_code=202)
async def analyze(
    payload: AnalyzeRequest,
    _token_data: TokenResponse = Depends(verify_bearer_token),
) -> AnalyzeEnqueueResponse:
    try:
        job = q.enqueue(
            process_analyze_job,
            payload.query,
            job_timeout=job_timeout_seconds(),
            result_ttl=result_ttl_seconds(),
            failure_ttl=failure_ttl_seconds(),
        )
        task_id = resolve_job_id(job)
        if not task_id:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível enfileirar o job.",
            )

        return AnalyzeEnqueueResponse(task_id=task_id, status="queued")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Falha ao enfileirar a analise.",
        ) from exc


@app.get("/status/{task_id}", response_model=AnalyzeStatusResponse)
async def get_status(task_id: str) -> AnalyzeStatusResponse:
    try:
        job = Job.fetch(task_id, connection=redis_conn)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail="Job não encontrado"
        ) from exc

    if job.is_queued:
        return AnalyzeStatusResponse(status="queued")
    if job.is_started:
        return AnalyzeStatusResponse(status="processing")
    if job.is_finished:
        result = job.result or {}
        return AnalyzeStatusResponse(
            status=result.get("status", "done"),
            result=AnalyzeResponse(
                query=result.get("query", ""),
                final_answer=result.get("final_answer"),
            ),
        )
    if job.is_failed:
        return AnalyzeStatusResponse(
            status="failed",
            error=str(job.exc_info),
        )

    return AnalyzeStatusResponse(status=job.get_status(refresh=True))


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
