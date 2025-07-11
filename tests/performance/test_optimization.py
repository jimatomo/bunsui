"""
パフォーマンス最適化のテスト
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
from src.bunsui.performance.cache import (
    CacheManager,
    MemoryCacheBackend,
    get_cache_manager,
    cached
)
from src.bunsui.performance.batch import (
    BatchProcessor,
    AsyncBatchProcessor,
    BatchProcessorFactory,
    BatchResult
)
from src.bunsui.performance.connection_pool import (
    ConnectionPool,
    AWSConnectionPool,
    get_aws_connection_pool
)
from src.bunsui.performance.profiler import (
    PerformanceMonitor,
    PerformanceProfiler,
    get_performance_monitor,
    profile_function
)


class TestCache:
    """キャッシュ機能のテスト"""

    @pytest.fixture
    def cache_manager(self):
        """キャッシュマネージャーを作成"""
        backend = MemoryCacheBackend(max_size=10)
        return CacheManager(backend)

    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_manager):
        """キャッシュの設定・取得テスト"""
        # 値を設定
        await cache_manager.set("test_key", "test_value", ttl=60)
        
        # 値を取得
        value = await cache_manager.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_manager):
        """キャッシュの期限切れテスト"""
        # 短いTTLで値を設定
        await cache_manager.set("test_key", "test_value", ttl=1)
        
        # すぐに取得
        value = await cache_manager.get("test_key")
        assert value == "test_value"
        
        # 1秒待ってから取得
        await asyncio.sleep(1.1)
        value = await cache_manager.get("test_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """キャッシュ統計のテスト"""
        # 値を設定・取得
        await cache_manager.set("key1", "value1")
        await cache_manager.set("key2", "value2")
        
        await cache_manager.get("key1")  # hit
        await cache_manager.get("key3")  # miss
        
        stats = cache_manager.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 2
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """キャッシュデコレータのテスト"""
        call_count = 0
        
        @cached(ttl=60)
        async def test_function(x):
            nonlocal call_count
            call_count += 1
            return f"result_{x}"
        
        # 初回呼び出し
        result1 = await test_function(1)
        assert result1 == "result_1"
        assert call_count == 1
        
        # 2回目呼び出し（キャッシュから取得）
        result2 = await test_function(1)
        assert result2 == "result_1"
        assert call_count == 1  # 呼び出し回数は増えない


class TestBatchProcessing:
    """バッチ処理のテスト"""

    def test_sync_batch_processor(self):
        """同期バッチプロセッサーのテスト"""
        def processor(item):
            return item * 2
        
        batch_processor = BatchProcessorFactory.create_sync_processor(
            processor=processor,
            batch_size=3,
            max_concurrent=2
        )
        
        items = [1, 2, 3, 4, 5]
        result = asyncio.run(batch_processor.process_batch(items))
        
        assert len(result.output_items) == 5
        assert result.output_items == [2, 4, 6, 8, 10]
        assert result.success_count == 5
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_async_batch_processor(self):
        """非同期バッチプロセッサーのテスト"""
        async def processor(item):
            await asyncio.sleep(0.01)  # 非同期処理をシミュレート
            return item * 2
        
        batch_processor = BatchProcessorFactory.create_async_processor(
            processor=processor,
            batch_size=3,
            max_concurrent=2
        )
        
        items = [1, 2, 3, 4, 5]
        result = await batch_processor.process_batch(items)
        
        assert len(result.output_items) == 5
        assert result.output_items == [2, 4, 6, 8, 10]
        assert result.success_count == 5
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_batch_processor_with_errors(self):
        """エラー処理のテスト"""
        def processor(item):
            if item == 3:
                raise ValueError("Test error")
            return item * 2
        
        batch_processor = BatchProcessorFactory.create_sync_processor(
            processor=processor,
            batch_size=2,
            max_concurrent=1
        )
        
        items = [1, 2, 3, 4]
        result = asyncio.run(batch_processor.process_batch(items))
        
        assert len(result.output_items) == 3  # 3つ成功
        assert result.success_count == 3
        assert result.error_count == 1
        assert len(result.errors) == 1


class TestConnectionPool:
    """接続プールのテスト"""

    @pytest.fixture
    def mock_factory(self):
        """モックファクトリーを作成"""
        mock_connection = Mock()
        mock_connection.close = Mock()
        
        def factory():
            return mock_connection
        
        return factory

    @pytest.mark.asyncio
    async def test_connection_pool(self, mock_factory):
        """接続プールのテスト"""
        pool = ConnectionPool(
            factory=mock_factory,
            min_size=2,
            max_size=5
        )
        
        await pool.start()
        
        try:
            # 接続を取得
            async with pool.get_connection() as conn1:
                assert conn1 is not None
            
            # 別の接続を取得
            async with pool.get_connection() as conn2:
                assert conn2 is not None
            
            # 統計を確認
            stats = pool.get_stats()
            assert stats["created"] >= 2
            assert stats["reused"] >= 0
            
        finally:
            await pool.stop()

    @pytest.mark.asyncio
    async def test_aws_connection_pool(self):
        """AWS接続プールのテスト"""
        pool = get_aws_connection_pool()
        
        # モックファクトリーを登録
        mock_factory = Mock()
        pool.register_service('test_service', mock_factory)
        
        await pool.start()
        
        try:
            # サービス接続を取得
            async with pool.get_service_connection('test_service') as conn:
                assert conn is not None
            
            # 統計を確認
            stats = pool.get_service_stats('test_service')
            assert stats is not None
            
        finally:
            await pool.stop()


class TestProfiler:
    """プロファイラーのテスト"""

    @pytest.fixture
    def profiler(self):
        """プロファイラーを作成"""
        return PerformanceProfiler()

    def test_profiler_function(self, profiler):
        """関数プロファイリングのテスト"""
        @profiler.profile_function
        def test_function():
            time.sleep(0.01)
            return "result"
        
        # 関数を実行
        result = test_function()
        assert result == "result"
        
        # 統計を確認
        stats = profiler.get_function_stats("test_function")
        assert stats is not None
        assert stats["total_calls"] == 1
        assert stats["avg_execution_time"] > 0

    @pytest.mark.asyncio
    async def test_profiler_context(self, profiler):
        """コンテキストプロファイリングのテスト"""
        async with profiler.profile_context("test_context"):
            await asyncio.sleep(0.01)
        
        # 統計を確認
        stats = profiler.get_function_stats("test_context")
        assert stats is not None
        assert stats["total_calls"] == 1
        assert stats["avg_execution_time"] > 0

    def test_performance_monitor(self):
        """パフォーマンスモニターのテスト"""
        monitor = get_performance_monitor()
        
        # モニタリングを開始
        monitor.start_monitoring()
        
        try:
            # プロファイリング対象の関数
            @monitor.profile_function
            def test_function():
                time.sleep(0.01)
                return "result"
            
            # 関数を実行
            result = test_function()
            assert result == "result"
            
            # 統計を確認
            stats = monitor.get_stats()
            assert "function_stats" in stats
            assert "memory_usage" in stats
            assert stats["monitoring_active"] is True
            
        finally:
            # モニタリングを停止
            monitor.stop_monitoring()


class TestIntegration:
    """統合テスト"""

    @pytest.mark.asyncio
    async def test_cache_with_batch_processing(self):
        """キャッシュとバッチ処理の統合テスト"""
        cache_manager = get_cache_manager()
        
        # バッチ処理でキャッシュを使用
        async def cached_processor(item):
            cache_key = f"processed_{item}"
            cached_result = await cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            # 処理をシミュレート
            result = item * 2
            await cache_manager.set(cache_key, result, ttl=60)
            return result
        
        batch_processor = BatchProcessorFactory.create_async_processor(
            processor=cached_processor,
            batch_size=3
        )
        
        items = [1, 2, 3, 1, 2]  # 重複あり
        result = await batch_processor.process_batch(items)
        
        assert len(result.output_items) == 5
        assert result.output_items == [2, 4, 6, 2, 4]
        assert result.success_count == 5
        
        # キャッシュ統計を確認
        cache_stats = cache_manager.get_stats()
        assert cache_stats["sets"] == 3  # ユニークな値のみキャッシュに保存
        assert cache_stats["hits"] == 2  # 重複した値はキャッシュから取得

    @pytest.mark.asyncio
    async def test_profiler_with_batch_processing(self):
        """プロファイラーとバッチ処理の統合テスト"""
        monitor = get_performance_monitor()
        monitor.start_monitoring()
        
        try:
            @monitor.profile_function
            async def slow_processor(item):
                await asyncio.sleep(0.01)
                return item * 2
            
            batch_processor = BatchProcessorFactory.create_async_processor(
                processor=slow_processor,
                batch_size=2
            )
            
            items = [1, 2, 3, 4]
            result = await batch_processor.process_batch(items)
            
            assert len(result.output_items) == 4
            assert result.success_count == 4
            
            # プロファイリング統計を確認
            stats = monitor.get_stats()
            assert "function_stats" in stats
            assert "slow_processor" in stats["function_stats"]
            
        finally:
            monitor.stop_monitoring()


if __name__ == "__main__":
    pytest.main([__file__]) 