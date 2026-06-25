from typing import Any, Optional


def resolve_job_id(job: Any | None) -> Optional[str]:
    """Compatibiliza leitura de id do job entre versões do RQ."""
    if job is None:
        return None

    job_id = getattr(job, "id", None)
    if job_id:
        return str(job_id)

    get_id = getattr(job, "get_id", None)
    if callable(get_id):
        return get_id()

    return None
