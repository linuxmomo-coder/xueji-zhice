from __future__ import annotations

import logging
import signal
import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.services.ai_reports import process_report_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("xueji-ai-worker")
_running = True


def _stop(_: int, __: object) -> None:
    global _running
    _running = False


def main() -> None:
    settings.validate_runtime()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)
    logger.info(
        "AI report worker started; queue=%s primary=%s fallback=%s",
        settings.ai_queue_name,
        settings.ai_primary_provider,
        settings.ai_fallback_provider,
    )
    while _running:
        try:
            item = client.blpop(settings.ai_queue_name, timeout=5)
        except RedisError as exc:
            logger.error("Redis queue error: %s", exc)
            time.sleep(5)
            continue
        if not item:
            continue
        _, report_id = item
        result = process_report_job(report_id)
        logger.info("AI report %s result=%s", report_id, result)
    logger.info("AI report worker stopped")


if __name__ == "__main__":
    main()
