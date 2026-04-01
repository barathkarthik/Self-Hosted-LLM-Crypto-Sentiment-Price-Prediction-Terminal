"""
Utilities — shared helpers used across the pipeline.
Retry-with-backoff ported from SRL (Strategy Research Lab):
  - live_dashboard.py  → defensive CSV retry pattern
  - live_executor.py   → resilient API call pattern
"""

import time
import logging
import functools

logger = logging.getLogger("Utils")


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                       backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Decorator: retries a function up to max_retries times with exponential backoff.

    Args:
        max_retries:  total attempts before giving up and re-raising
        base_delay:   seconds to wait after first failure
        backoff:      multiplier applied to delay after each failure
        exceptions:   exception types to catch and retry on

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0, backoff=2.0)
        def fetch_data():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            f"[{func.__name__}] Failed after {max_retries} attempts: {e}"
                        )
                        raise
                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator
