import os

from dotenv import load_dotenv
from redis import Redis
from rq import Queue


load_dotenv()
load_dotenv(".env.qdrant")


def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")


def queue_name() -> str:
    return os.getenv("RQ_QUEUE_NAME", "completions")


def job_timeout_seconds() -> int:
    return int(os.getenv("RQ_JOB_TIMEOUT_SECONDS", "600"))


def result_ttl_seconds() -> int:
    return int(os.getenv("RQ_RESULT_TTL_SECONDS", "86400"))


def failure_ttl_seconds() -> int:
    return int(os.getenv("RQ_FAILURE_TTL_SECONDS", "86400"))


def retry_intervals() -> list[int]:
    """Return the configured delays between retries of an analysis job."""
    value = os.getenv(
        "RQ_RETRY_INTERVALS_SECONDS",
        "30,60,120,300,600",
    )
    return [
        int(interval.strip())
        for interval in value.split(",")
        if interval.strip()
    ]


def final_results_queue_name() -> str:
    return os.getenv("FINAL_RESULTS_QUEUE_NAME", "final-results")


def final_results_job_timeout_seconds() -> int:
    return int(os.getenv("FINAL_RESULTS_JOB_TIMEOUT_SECONDS", "60"))


def final_results_result_ttl_seconds() -> int:
    return int(os.getenv("FINAL_RESULTS_RESULT_TTL_SECONDS", "86400"))


def final_results_failure_ttl_seconds() -> int:
    return int(os.getenv("FINAL_RESULTS_FAILURE_TTL_SECONDS", "604800"))


def final_results_retry_intervals() -> list[int]:
    value = os.getenv(
        "FINAL_RESULTS_RETRY_INTERVALS_SECONDS",
        "10,30,60,300,900",
    )
    return [
        int(interval.strip())
        for interval in value.split(",")
        if interval.strip()
    ]


def qdrant_queue_name() -> str:
    return os.getenv("QDRANT_QUEUE_NAME", "qdrant")


def qdrant_enabled() -> bool:
    return os.getenv("QDRANT_ENABLED", "true").strip().lower() == "true"


def qdrant_job_timeout_seconds() -> int:
    return int(os.getenv("QDRANT_JOB_TIMEOUT_SECONDS", "900"))


def qdrant_result_ttl_seconds() -> int:
    return int(os.getenv("QDRANT_RESULT_TTL_SECONDS", "86400"))


def qdrant_failure_ttl_seconds() -> int:
    return int(os.getenv("QDRANT_FAILURE_TTL_SECONDS", "604800"))


def qdrant_retry_intervals() -> list[int]:
    value = os.getenv(
        "QDRANT_RETRY_INTERVALS_SECONDS",
        "60,300,900",
    )
    return [
        int(interval.strip())
        for interval in value.split(",")
        if interval.strip()
    ]


def get_redis_connection() -> Redis:
    return Redis.from_url(redis_url())


def get_queue() -> Queue:
    return Queue(name=queue_name(), connection=get_redis_connection())


def get_final_results_queue() -> Queue:
    return Queue(
        name=final_results_queue_name(),
        connection=get_redis_connection(),
    )


def get_qdrant_queue() -> Queue:
    return Queue(
        name=qdrant_queue_name(),
        connection=get_redis_connection(),
    )
