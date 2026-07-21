import os

from redis import Redis
from rq import Queue


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


def get_redis_connection() -> Redis:
    return Redis.from_url(redis_url())


def get_queue() -> Queue:
    return Queue(name=queue_name(), connection=get_redis_connection())


def get_final_results_queue() -> Queue:
    return Queue(
        name=final_results_queue_name(),
        connection=get_redis_connection(),
    )
