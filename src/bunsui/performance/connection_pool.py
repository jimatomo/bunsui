"""
接続プーリングシステム

AWSサービスとの接続を効率的に管理するための接続プール機能を提供します。
"""

import asyncio
from typing import Any, Dict, List, Optional, TypeVar, Generic, Callable, Union
from dataclasses import dataclass
from datetime import datetime
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ConnectionInfo:
    """接続情報"""
    connection: Any
    created_at: datetime
    last_used: datetime
    use_count: int = 0
    is_active: bool = True

    def mark_used(self):
        """使用記録"""
        self.last_used = datetime.now()
        self.use_count += 1


class ConnectionPool(Generic[T]):
    """接続プール"""

    def __init__(
        self,
        factory: Callable[[], Union[T, Any]],
        min_size: int = 5,
        max_size: int = 20,
        max_age: int = 300,  # 5分
        max_idle: int = 60,   # 1分
        check_interval: int = 30  # 30秒
    ):
        self.factory = factory
        self.min_size = min_size
        self.max_size = max_size
        self.max_age = max_age
        self.max_idle = max_idle
        self.check_interval = check_interval
        
        self._pool: List[ConnectionInfo] = []
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stats = {
            "created": 0,
            "reused": 0,
            "closed": 0,
            "errors": 0
        }

    async def start(self):
        """プールを開始"""
        # 最小接続数を確保
        await self._ensure_min_connections()
        
        # クリーンアップタスクを開始
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        """プールを停止"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 全接続を閉じる
        async with self._lock:
            for conn_info in self._pool:
                await self._close_connection(conn_info.connection)
            self._pool.clear()

    @asynccontextmanager
    async def get_connection(self):
        """接続を取得"""
        connection = await self._get_connection()
        try:
            yield connection
        finally:
            await self._return_connection(connection)

    async def _get_connection(self) -> T:
        """接続を取得"""
        async with self._lock:
            # 利用可能な接続を探す
            for conn_info in self._pool:
                if conn_info.is_active and not self._is_expired(conn_info):
                    conn_info.mark_used()
                    self._stats["reused"] += 1
                    logger.debug("Reusing connection from pool")
                    return conn_info.connection

            # 新しい接続を作成
            if len(self._pool) < self.max_size:
                connection = await self._create_connection()
                conn_info = ConnectionInfo(
                    connection=connection,
                    created_at=datetime.now(),
                    last_used=datetime.now()
                )
                self._pool.append(conn_info)
                self._stats["created"] += 1
                logger.debug("Created new connection")
                return connection

            # プールが満杯の場合、最も古い接続を再利用
            oldest_conn = min(self._pool, key=lambda x: x.last_used)
            oldest_conn.mark_used()
            self._stats["reused"] += 1
            logger.debug("Reusing oldest connection")
            return oldest_conn.connection

    async def _return_connection(self, connection: T):
        """接続を返却"""
        # 接続プールでは接続を返却するだけで、実際には閉じない
        pass

    async def _create_connection(self) -> T:
        """新しい接続を作成"""
        try:
            if asyncio.iscoroutinefunction(self.factory):
                return await self.factory()
            else:
                return self.factory()
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Failed to create connection: {e}")
            raise

    async def _close_connection(self, connection: T):
        """接続を閉じる"""
        try:
            if hasattr(connection, 'close'):
                close_method = getattr(connection, 'close')
                if asyncio.iscoroutinefunction(close_method):
                    await close_method()
                else:
                    close_method()
            elif hasattr(connection, 'aclose'):
                aclose_method = getattr(connection, 'aclose')
                await aclose_method()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    def _is_expired(self, conn_info: ConnectionInfo) -> bool:
        """接続が期限切れかチェック"""
        now = datetime.now()
        
        # 最大年齢チェック
        if (now - conn_info.created_at).total_seconds() > self.max_age:
            return True
        
        # 最大アイドル時間チェック
        if (now - conn_info.last_used).total_seconds() > self.max_idle:
            return True
        
        return False

    async def _ensure_min_connections(self):
        """最小接続数を確保"""
        while len(self._pool) < self.min_size:
            try:
                connection = await self._create_connection()
                conn_info = ConnectionInfo(
                    connection=connection,
                    created_at=datetime.now(),
                    last_used=datetime.now()
                )
                self._pool.append(conn_info)
                self._stats["created"] += 1
            except Exception as e:
                logger.error(f"Failed to create minimum connection: {e}")
                break

    async def _cleanup_loop(self):
        """クリーンアップループ"""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self._cleanup_expired_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_expired_connections(self):
        """期限切れ接続をクリーンアップ"""
        async with self._lock:
            expired_connections = []
            
            for conn_info in self._pool:
                if self._is_expired(conn_info):
                    expired_connections.append(conn_info)
                    conn_info.is_active = False

            # 期限切れ接続を閉じる
            for conn_info in expired_connections:
                await self._close_connection(conn_info.connection)
                self._pool.remove(conn_info)
                self._stats["closed"] += 1

            # 最小接続数を確保
            await self._ensure_min_connections()

    def get_stats(self) -> Dict[str, Any]:
        """プール統計を取得"""
        return {
            **self._stats,
            "pool_size": len(self._pool),
            "active_connections": len([c for c in self._pool if c.is_active]),
            "min_size": self.min_size,
            "max_size": self.max_size
        }


class AWSConnectionPool:
    """AWS接続プール"""

    def __init__(self):
        self._pools: Dict[str, ConnectionPool] = {}

    def register_service(
        self,
        service_name: str,
        factory: Callable[[], Any],
        min_size: int = 5,
        max_size: int = 20
    ):
        """サービスを登録"""
        pool = ConnectionPool(
            factory=factory,
            min_size=min_size,
            max_size=max_size
        )
        self._pools[service_name] = pool

    async def start(self):
        """全プールを開始"""
        for pool in self._pools.values():
            await pool.start()

    async def stop(self):
        """全プールを停止"""
        for pool in self._pools.values():
            await pool.stop()

    @asynccontextmanager
    async def get_service_connection(self, service_name: str):
        """サービス接続を取得"""
        if service_name not in self._pools:
            raise ValueError(f"Service {service_name} not registered")
        
        async with self._pools[service_name].get_connection() as connection:
            yield connection

    def get_service_stats(self, service_name: str) -> Optional[Dict[str, Any]]:
        """サービス統計を取得"""
        if service_name not in self._pools:
            return None
        return self._pools[service_name].get_stats()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """全サービス統計を取得"""
        return {
            service_name: pool.get_stats()
            for service_name, pool in self._pools.items()
        }


# グローバルAWS接続プール
_aws_connection_pool: Optional[AWSConnectionPool] = None


def get_aws_connection_pool() -> AWSConnectionPool:
    """AWS接続プールを取得"""
    global _aws_connection_pool
    if _aws_connection_pool is None:
        _aws_connection_pool = AWSConnectionPool()
    return _aws_connection_pool


# 使用例
async def example_usage():
    """使用例"""
    
    # AWS接続プールを設定
    pool = get_aws_connection_pool()
    
    # S3クライアントプールを登録
    def create_s3_client():
        import boto3
        return boto3.client('s3')
    
    pool.register_service('s3', create_s3_client, min_size=3, max_size=10)
    
    # Lambdaクライアントプールを登録
    def create_lambda_client():
        import boto3
        return boto3.client('lambda')
    
    pool.register_service('lambda', create_lambda_client, min_size=2, max_size=8)
    
    # プールを開始
    await pool.start()
    
    try:
        # S3接続を使用
        async with pool.get_service_connection('s3') as s3_client:
            # S3操作を実行
            response = s3_client.list_buckets()
            print(f"Found {len(response['Buckets'])} buckets")
        
        # Lambda接続を使用
        async with pool.get_service_connection('lambda') as lambda_client:
            # Lambda操作を実行
            response = lambda_client.list_functions()
            print(f"Found {len(response['Functions'])} functions")
        
        # 統計を表示
        stats = pool.get_all_stats()
        print("Connection pool stats:", stats)
        
    finally:
        # プールを停止
        await pool.stop()


if __name__ == "__main__":
    asyncio.run(example_usage()) 