"""Best-effort result cache. A cache outage must never fail a request."""
from __future__ import annotations

import json
import logging
from typing import Protocol

log = logging.getLogger("nlp_api.cache")


class Cache(Protocol):
    async def get_many(self, keys: list[str]) -> list[dict | None]: ...
    async def set_many(self, items: dict[str, dict], ttl: int) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class NullCache:
    async def get_many(self, keys): return [None] * len(keys)
    async def set_many(self, items, ttl): return None
    async def ping(self): return True
    async def close(self): return None


class DictCache(NullCache):
    """In-memory cache for tests."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}

    async def get_many(self, keys): return [self.store.get(k) for k in keys]
    async def set_many(self, items, ttl): self.store.update(items)


class RedisCache:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._r = redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25)

    async def get_many(self, keys):
        try:
            vals = await self._r.mget(keys)
            return [json.loads(v) if v else None for v in vals]
        except Exception as exc:  # noqa: BLE001
            log.warning("cache get failed: %s", exc)
            return [None] * len(keys)

    async def set_many(self, items, ttl):
        try:
            pipe = self._r.pipeline()
            for k, v in items.items():
                pipe.set(k, json.dumps(v), ex=ttl)
            await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("cache set failed: %s", exc)

    async def ping(self):
        try:
            return bool(await self._r.ping())
        except Exception:  # noqa: BLE001
            return False

    async def close(self):
        await self._r.aclose()


def build_cache(url: str) -> Cache:
    return RedisCache(url) if url else NullCache()
