import asyncio
import logging
import traceback

from fp.main import run_foul_play

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        asyncio.run(run_foul_play())
    except Exception:
        logger.error(traceback.format_exc())
        raise
