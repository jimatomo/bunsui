"""
キャッシュ管理システム

パフォーマンス向上のためのキャッシュ機能を提供します。
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        """キャッシュが期限切れかチェック"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def access(self):
        """アクセス記録"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class CacheBackend(ABC):
    """キャッシュバックエンドの抽象クラス"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """値を設定"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """値を削除"""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """全キャッシュをクリア"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """キーの存在確認"""
        pass


class MemoryCacheBackend(CacheBackend):
    """メモリキャッシュバックエンド"""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                del self._cache[key]
                return None

            entry.access()
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            # キャッシュサイズ制限チェック
            if len(self._cache) >= self._max_size:
                await self._evict_least_used()

            expires_at = None
            if ttl is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl)

            self._cache[key] = CacheEntry(
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at
            )

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                return False
            return True

    async def _evict_least_used(self):
        """最も使用頻度の低いエントリを削除"""
        if not self._cache:
            return

        # LRU（Least Recently Used）アルゴリズム
        least_used = min(
            self._cache.items(),
            key=lambda x: (x[1].access_count, x[1].last_accessed)
        )
        del self._cache[least_used[0]]


class RedisCacheBackend(CacheBackend):
    """Redisキャッシュバックエンド"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        """Redis接続を取得"""
        if self._redis is None:
            import aioredis
            self._redis = await aioredis.from_url(self.redis_url)
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        redis = await self._get_redis()
        value = await redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        redis = await self._get_redis()
        serialized = json.dumps(value)
        if ttl is not None:
            await redis.setex(key, ttl, serialized)
        else:
            await redis.set(key, serialized)

    async def delete(self, key: str) -> None:
        redis = await self._get_redis()
        await redis.delete(key)

    async def clear(self) -> None:
        redis = await self._get_redis()
        await redis.flushdb()

    async def exists(self, key: str) -> bool:
        redis = await self._get_redis()
        return await redis.exists(key) > 0


class CacheManager:
    """キャッシュマネージャー"""

    def __init__(self, backend: CacheBackend):
        self.backend = backend
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        value = await self.backend.get(key)
        if value is not None:
            self._stats["hits"] += 1
            logger.debug(f"Cache hit: {key}")
        else:
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {key}")
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """値を設定"""
        await self.backend.set(key, value, ttl)
        self._stats["sets"] += 1
        logger.debug(f"Cache set: {key} (ttl: {ttl})")

    async def delete(self, key: str) -> None:
        """値を削除"""
        await self.backend.delete(key)
        self._stats["deletes"] += 1
        logger.debug(f"Cache delete: {key}")

    async def clear(self) -> None:
        """全キャッシュをクリア"""
        await self.backend.clear()
        logger.info("Cache cleared")

    async def exists(self, key: str) -> bool:
        """キーの存在確認"""
        return await self.backend.exists(key)

    def get_stats(self) -> Dict[str, Union[int, float]]:
        """キャッシュ統計を取得"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate
        }

    async def invalidate_pattern(self, pattern: str) -> None:
        """パターンにマッチするキーを無効化"""
        # メモリキャッシュの場合のみ実装
        if isinstance(self.backend, MemoryCacheBackend):
            async with self.backend._lock:
                keys_to_delete = [
                    key for key in self.backend._cache.keys()
                    if pattern in key
                ]
                for key in keys_to_delete:
                    await self.delete(key)


# デフォルトキャッシュマネージャー
_default_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """デフォルトキャッシュマネージャーを取得"""
    global _default_cache_manager
    if _default_cache_manager is None:
        backend = MemoryCacheBackend()
        _default_cache_manager = CacheManager(backend)
    return _default_cache_manager


def set_cache_manager(manager: CacheManager) -> None:
    """デフォルトキャッシュマネージャーを設定"""
    global _default_cache_manager
    _default_cache_manager = manager


# デコレータ
def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """キャッシュデコレータ"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()
            
            # キャッシュキー生成
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # キャッシュから取得を試行
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 関数実行
            result = await func(*args, **kwargs)
            
            # キャッシュに保存
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator 