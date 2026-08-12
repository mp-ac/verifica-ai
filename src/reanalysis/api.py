from fastapi import APIRouter, Depends, HTTPException
from rq.job import Job
from starlette.concurrency import run_in_threadpool

from auth import TokenResponse, verify_bearer_token
from reanalysis.job import process_reanalyze_job
from reanalysis.result_delivery import (
    deliver_completed_reanalysis,
    deliver_failed_reanalysis,
    deliver_stopped_reanalysis,
)
from reanalysis.schemas import (
    ReanalyzeEnqueueResponse,
    ReanalyzeRequest,
    ReanalysisResponse,
    ReanalysisStatusResponse,
)
from reanalysis.verificaai_painel import (
    FinalResultAlreadyReviewedError,
    PanelApiError,
    PanelFinalResultNotFoundError,
    fetch_final_result,
)
from queueing import (
    failure_ttl_seconds,
    get_queue,
    job_timeout_seconds,
    result_ttl_seconds,
)
from utils.job_utils import resolve_job_id


router = APIRouter(tags=["reanalysis"])
q = get_queue()


@router.post(
    "/reanalyze",
    response_model=ReanalyzeEnqueueResponse,
    status_code=202,
)
async def reanalyze(
    payload: ReanalyzeRequest,
    _token_data: TokenResponse = Depends(verify_bearer_token),
) -> ReanalyzeEnqueueResponse:
    try:
        final_result = await run_in_threadpool(
            fetch_final_result,
            payload.final_result_id,
        )
    except PanelFinalResultNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FinalResultAlreadyReviewedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PanelApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        job = await run_in_threadpool(
            q.enqueue,
            process_reanalyze_job,
            str(payload.reanalysis_id),
            final_result.model_dump(mode="json"),
            payload.prompt,
            job_timeout=job_timeout_seconds(),
            result_ttl=result_ttl_seconds(),
            failure_ttl=failure_ttl_seconds(),
            on_success=deliver_completed_reanalysis,
            on_failure=deliver_failed_reanalysis,
            on_stopped=deliver_stopped_reanalysis,
        )
        task_id = resolve_job_id(job)
        if not task_id:
            raise HTTPException(
                status_code=500,
                detail="Não foi possível enfileirar a reanálise.",
            )

        return ReanalyzeEnqueueResponse(task_id=task_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Falha ao enfileirar a reanálise.",
        ) from exc


@router.get(
    "/reanalyze/status/{task_id}",
    response_model=ReanalysisStatusResponse,
)
async def get_reanalysis_status(
    task_id: str,
    _token_data: TokenResponse = Depends(verify_bearer_token),
) -> ReanalysisStatusResponse:
    try:
        job = await run_in_threadpool(
            Job.fetch,
            task_id,
            connection=q.connection,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Job não encontrado") from exc

    if job.is_queued:
        return ReanalysisStatusResponse(status="queued")
    if job.is_started:
        return ReanalysisStatusResponse(status="processing")
    if job.is_finished:
        result = job.result or {}
        return ReanalysisStatusResponse(
            status=result.get("status", "done"),
            result=ReanalysisResponse.model_validate(result.get("result")),
            execution=result.get("execution"),
            error=result.get("error"),
        )
    if job.is_failed:
        return ReanalysisStatusResponse(
            status="failed",
            error=str(job.exc_info),
        )

    return ReanalysisStatusResponse(status=job.get_status(refresh=True))
