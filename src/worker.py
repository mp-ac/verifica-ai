from redis import Redis
from rq import Queue, Worker

from queueing import queue_name, redis_url


def main() -> None:
    conn = Redis.from_url(redis_url())
    queues = [Queue(queue_name(), connection=conn)]
    worker = Worker(queues, connection=conn)
    worker.work()


if __name__ == "__main__":
    main()
