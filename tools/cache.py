"""
═══════════════════════════════════════════════════════════════════
 APEX CODING AGENT — Redis Cache & State Persistence
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Optional

import redis.asyncio as aioredis
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)


class StateCache:
    """
    Redis-backed state persistence and caching.
    - Session snapshots for crash recovery
    - Agent output caching to avoid re-computation
    - Pub/Sub for real-time progress streaming
    """

    def __init__(self):
        settings = get_settings()
        self._pool: Optional[aioredis.ConnectionPool] = None
        self._redis: Optional[aioredis.Redis] = None
        self._url = settings.redis_url
        self._password = settings.redis_password
        self._max_connections = settings.redis_max_connections

    async def connect(self) -> None:
        self._pool = aioredis.ConnectionPool.from_url(
            self._url,
            password=self._password,
            max_connections=self._max_connections,
            decode_responses=True,
        )
        self._redis = aioredis.Redis(connection_pool=self._pool)
        await self._redis.ping()
        logger.info("cache.connected", url=self._url)

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()
        if self._pool:
            await self._pool.disconnect()
        logger.info("cache.disconnected")

    @property
    def redis(self) -> aioredis.Redis:
        if not self._redis:
            raise RuntimeError("Cache not connected. Call connect() first.")
        return self._redis

    # ── Session Snapshots ───────────────────────────────────────

    async def save_session(self, session_id: str, state: dict[str, Any], ttl_hours: int = 24) -> None:
        key = f"apex:session:{session_id}"
        await self.redis.setex(key, timedelta(hours=ttl_hours), json.dumps(state, default=str))
        logger.debug("cache.session.saved", session_id=session_id)

    async def load_session(self, session_id: str) -> Optional[dict[str, Any]]:
        key = f"apex:session:{session_id}"
        data = await self.redis.get(key)
        if data:
            logger.debug("cache.session.loaded", session_id=session_id)
            return json.loads(data)
        return None

    async def delete_session(self, session_id: str) -> None:
        await self.redis.delete(f"apex:session:{session_id}")

    # ── Agent Output Cache ──────────────────────────────────────

    async def cache_agent_output(
        self, session_id: str, agent: str, output: dict[str, Any], ttl_minutes: int = 60
    ) -> None:
        key = f"apex:agent:{session_id}:{agent}"
        await self.redis.setex(key, timedelta(minutes=ttl_minutes), json.dumps(output, default=str))

    async def get_cached_output(self, session_id: str, agent: str) -> Optional[dict[str, Any]]:
        key = f"apex:agent:{session_id}:{agent}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    # ── Progress Pub/Sub ────────────────────────────────────────

    async def publish_progress(self, session_id: str, event: dict[str, Any]) -> None:
        channel = f"apex:progress:{session_id}"
        await self.redis.publish(channel, json.dumps(event, default=str))

    async def subscribe_progress(self, session_id: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"apex:progress:{session_id}")
        return pubsub

    # ── Dead Letter Queue ───────────────────────────────────────

    async def push_dead_letter(self, session_id: str, failure: dict[str, Any]) -> None:
        key = f"apex:dlq:{session_id}"
        await self.redis.rpush(key, json.dumps(failure, default=str))
        await self.redis.expire(key, timedelta(hours=72))

    async def get_dead_letters(self, session_id: str) -> list[dict[str, Any]]:
        key = f"apex:dlq:{session_id}"
        items = await self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in items]

    # ── Metrics ─────────────────────────────────────────────────

    async def increment_metric(self, metric: str, value: int = 1) -> None:
        await self.redis.incrby(f"apex:metrics:{metric}", value)

    async def get_metric(self, metric: str) -> int:
        val = await self.redis.get(f"apex:metrics:{metric}")
        return int(val) if val else 0


# Singleton instance
_cache: Optional[StateCache] = None


async def get_cache() -> StateCache:
    global _cache
    if _cache is None:
        _cache = StateCache()
        try:
            await _cache.connect()
        except Exception as exc:
            logger.warning("cache.connect.failed", error=str(exc), hint="Running without Redis")
            _cache = StateCache()  # Return unconnected instance
    return _cache
