from __future__ import annotations

import logging
import signal
import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.services.question_quality import REGRADING_QUEUE, process_regrade_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("xueji-regrade-worker")
_running = True


def _stop(_: int, __: object) -> None:
    global _running
    _running = False


def main() -> None:
    settings.validate_runtime()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)
    logger.info("Answer regrade worker started; queue=%s", REGRADING_QUEUE)
    while _running:
        try:
            item = client.blpop(REGRADING_QUEUE, timeout=5)
        except RedisError as exc:
            logger.error("Redis queue error: %s", exc)
            time.sleep(5)
            continue
        if not item:
            continue
        _, job_id = item
        result = process_regrade_job(job_id)
        logger.info("Regrade job %s result=%s", job_id, result)
    logger.info("Answer regrade worker stopped")


if __name__ == "__main__":
    main()
