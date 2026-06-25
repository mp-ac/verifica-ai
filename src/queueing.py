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


def get_redis_connection() -> Redis:
    return Redis.from_url(redis_url())


def get_queue() -> Queue:
    return Queue(name=queue_name(), connection=get_redis_connection())
