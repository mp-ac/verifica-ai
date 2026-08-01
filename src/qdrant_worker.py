from redis import Redis
from rq import Queue, Worker

from qdrant import try_ensure_collection
from queueing import qdrant_queue_name, redis_url


def main() -> None:
    try_ensure_collection()

    conn = Redis.from_url(redis_url())
    queues = [Queue(qdrant_queue_name(), connection=conn)]
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
