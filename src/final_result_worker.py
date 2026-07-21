from redis import Redis
from rq import Queue, Worker

from queueing import final_results_queue_name, redis_url


def main() -> None:
    conn = Redis.from_url(redis_url())
    queues = [Queue(final_results_queue_name(), connection=conn)]
    worker = Worker(queues, connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
