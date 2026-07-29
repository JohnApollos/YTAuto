import os
from datetime import datetime
from zoneinfo import ZoneInfo
import redis
from autonomous_media.config import settings
from autonomous_media.logging import get_logger

logger = get_logger("quota")

class QuotaTracker:
    def __init__(self, redis_url: str = settings.redis_url):
        self.redis_url = redis_url
        self._redis = None
        self._in_memory_quota = {}  # Fallback for testing / unavailable Redis

        # Don't try to connect to real Redis if we are in test env or redis is disabled
        if os.environ.get("MODEL_ENV") != "test" and os.environ.get("YOUTUBE_API_ENV") != "test":
            try:
                self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Could not connect to Redis at {redis_url}, falling back to in-memory: {e}")

    def _get_key(self, project_id: str) -> str:
        # Daily quota resets at midnight Pacific time
        tz = ZoneInfo("America/Los_Angeles")
        date_str = datetime.now(tz).strftime("%Y-%m-%d")
        return f"quota:{project_id}:{date_str}:remaining"

    def get_remaining_quota(self, project_id: str) -> int:
        key = self._get_key(project_id)
        if self._redis:
            try:
                val = self._redis.get(key)
                if val is None:
                    # Initialize to 10,000 units
                    self._redis.set(key, 10000, ex=172800) # Expire after 48h
                    return 10000
                return int(val)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}. Using fallback.")
        
        # Fallback
        return self._in_memory_quota.setdefault(key, 10000)

    def has_quota(self, project_id: str, amount: int) -> bool:
        remaining = self.get_remaining_quota(project_id)
        return remaining >= amount

    def consume_quota(self, project_id: str, amount: int):
        key = self._get_key(project_id)
        logger.info(f"Consuming {amount} quota units for project {project_id}")
        if self._redis:
            try:
                # decrby will auto-initialize to 0 first if it doesn't exist, which we don't want.
                # So we check/get first to ensure it's initialized to 10000.
                self.get_remaining_quota(project_id)
                self._redis.decrby(key, amount)
                return
            except Exception as e:
                logger.warning(f"Redis decrby failed: {e}. Using fallback.")

        # Fallback
        remaining = self._in_memory_quota.setdefault(key, 10000)
        self._in_memory_quota[key] = max(0, remaining - amount)

# Global singleton
quota_tracker = QuotaTracker()
