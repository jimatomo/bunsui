"""
プロファイリングツール

パフォーマンス分析と最適化のためのプロファイリング機能を提供します。
"""

import asyncio
import time
import cProfile
import pstats
import io
import tracemalloc
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager
import logging
import functools

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    function_name: str
    execution_time: float
    memory_usage: int
    call_count: int
    avg_time: float
    min_time: float
    max_time: float
    timestamp: datetime = field(default_factory=datetime.now)


class PerformanceProfiler:
    """パフォーマンスプロファイラー"""

    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetrics]] = {}
        self.active_profilers: Dict[str, Any] = {}
        self.tracemalloc_started = False

    def start_tracemalloc(self):
        """メモリトレースを開始"""
        if not self.tracemalloc_started:
            tracemalloc.start()
            self.tracemalloc_started = True
            logger.info("Memory tracing started")

    def stop_tracemalloc(self):
        """メモリトレースを停止"""
        if self.tracemalloc_started:
            tracemalloc.stop()
            self.tracemalloc_started = False
            logger.info("Memory tracing stopped")

    def get_memory_usage(self) -> int:
        """現在のメモリ使用量を取得"""
        if self.tracemalloc_started:
            current, peak = tracemalloc.get_traced_memory()
            return current
        return 0

    def profile_function(self, func: Callable) -> Callable:
        """関数をプロファイリング"""
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = self.get_memory_usage()
            
            try:
                result = await func(*args, **kwargs)
            finally:
                end_time = time.time()
                end_memory = self.get_memory_usage()
                
                execution_time = end_time - start_time
                memory_usage = end_memory - start_memory
                
                self._record_metrics(
                    func.__name__,
                    execution_time,
                    memory_usage
                )
            
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = self.get_memory_usage()
            
            try:
                result = func(*args, **kwargs)
            finally:
                end_time = time.time()
                end_memory = self.get_memory_usage()
                
                execution_time = end_time - start_time
                memory_usage = end_memory - start_memory
                
                self._record_metrics(
                    func.__name__,
                    execution_time,
                    memory_usage
                )
            
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    def _record_metrics(self, function_name: str, execution_time: float, memory_usage: int):
        """メトリクスを記録"""
        if function_name not in self.metrics:
            self.metrics[function_name] = []

        metrics = PerformanceMetrics(
            function_name=function_name,
            execution_time=execution_time,
            memory_usage=memory_usage,
            call_count=1,
            avg_time=execution_time,
            min_time=execution_time,
            max_time=execution_time
        )

        self.metrics[function_name].append(metrics)

        # 統計を更新
        if len(self.metrics[function_name]) > 1:
            prev_metrics = self.metrics[function_name][-2]
            metrics.call_count = prev_metrics.call_count + 1
            metrics.avg_time = (prev_metrics.avg_time * prev_metrics.call_count + execution_time) / metrics.call_count
            metrics.min_time = min(prev_metrics.min_time, execution_time)
            metrics.max_time = max(prev_metrics.max_time, execution_time)

    @asynccontextmanager
    async def profile_context(self, context_name: str):
        """コンテキストプロファイリング"""
        start_time = time.time()
        start_memory = self.get_memory_usage()
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self.get_memory_usage()
            
            execution_time = end_time - start_time
            memory_usage = end_memory - start_memory
            
            self._record_metrics(
                context_name,
                execution_time,
                memory_usage
            )

    def get_function_stats(self, function_name: str) -> Optional[Dict[str, Any]]:
        """関数統計を取得"""
        if function_name not in self.metrics or not self.metrics[function_name]:
            return None

        metrics_list = self.metrics[function_name]
        latest = metrics_list[-1]
        
        return {
            "function_name": function_name,
            "total_calls": latest.call_count,
            "avg_execution_time": latest.avg_time,
            "min_execution_time": latest.min_time,
            "max_execution_time": latest.max_time,
            "latest_execution_time": latest.execution_time,
            "latest_memory_usage": latest.memory_usage,
            "timestamp": latest.timestamp
        }

    def get_all_stats(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """全関数統計を取得"""
        return {
            function_name: self.get_function_stats(function_name)
            for function_name in self.metrics.keys()
        }

    def clear_metrics(self, function_name: Optional[str] = None):
        """メトリクスをクリア"""
        if function_name:
            self.metrics.pop(function_name, None)
        else:
            self.metrics.clear()

    def export_profile_data(self, filename: str):
        """プロファイルデータをエクスポート"""
        import json
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for function_name, metrics_list in self.metrics.items():
            data["metrics"][function_name] = [
                {
                    "execution_time": m.execution_time,
                    "memory_usage": m.memory_usage,
                    "call_count": m.call_count,
                    "avg_time": m.avg_time,
                    "min_time": m.min_time,
                    "max_time": m.max_time,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in metrics_list
            ]
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)


class CPythonProfiler:
    """CPythonプロファイラー"""

    def __init__(self):
        self.profiler = None
        self.stats = None

    def start_profiling(self):
        """プロファイリングを開始"""
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        logger.info("CPython profiling started")

    def stop_profiling(self):
        """プロファイリングを停止"""
        if self.profiler:
            self.profiler.disable()
            s = io.StringIO()
            self.stats = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
            self.stats.print_stats()
            logger.info("CPython profiling stopped")
            return s.getvalue()
        return ""

    def get_stats(self) -> Optional[pstats.Stats]:
        """統計を取得"""
        return self.stats


class PerformanceMonitor:
    """パフォーマンスモニター"""

    def __init__(self):
        self.profiler = PerformanceProfiler()
        self.cpython_profiler = CPythonProfiler()
        self.monitoring_active = False

    def start_monitoring(self):
        """モニタリングを開始"""
        self.profiler.start_tracemalloc()
        self.cpython_profiler.start_profiling()
        self.monitoring_active = True
        logger.info("Performance monitoring started")

    def stop_monitoring(self) -> str:
        """モニタリングを停止"""
        if not self.monitoring_active:
            return ""

        self.profiler.stop_tracemalloc()
        cpython_stats = self.cpython_profiler.stop_profiling()
        self.monitoring_active = False
        
        logger.info("Performance monitoring stopped")
        return cpython_stats

    def profile_function(self, func: Callable) -> Callable:
        """関数をプロファイリング"""
        return self.profiler.profile_function(func)

    @asynccontextmanager
    async def profile_context(self, context_name: str):
        """コンテキストプロファイリング"""
        async with self.profiler.profile_context(context_name):
            yield

    def get_stats(self) -> Dict[str, Any]:
        """統計を取得"""
        return {
            "function_stats": self.profiler.get_all_stats(),
            "memory_usage": self.profiler.get_memory_usage(),
            "monitoring_active": self.monitoring_active
        }

    def export_data(self, filename: str):
        """データをエクスポート"""
        self.profiler.export_profile_data(filename)


# グローバルパフォーマンスモニター
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """パフォーマンスモニターを取得"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# デコレータ
def profile_function(func: Callable) -> Callable:
    """関数プロファイリングデコレータ"""
    monitor = get_performance_monitor()
    return monitor.profile_function(func)


# 使用例
async def example_usage():
    """使用例"""
    
    monitor = get_performance_monitor()
    
    # モニタリングを開始
    monitor.start_monitoring()
    
    # プロファイリング対象の関数
    @profile_function
    async def slow_function():
        await asyncio.sleep(0.1)
        return "result"
    
    # 関数を実行
    for _ in range(5):
        await slow_function()
    
    # コンテキストプロファイリング
    async with monitor.profile_context("batch_processing"):
        for _ in range(3):
            await asyncio.sleep(0.05)
    
    # 統計を表示
    stats = monitor.get_stats()
    print("Performance stats:", stats)
    
    # モニタリングを停止
    cpython_stats = monitor.stop_monitoring()
    print("CPython stats:", cpython_stats)


if __name__ == "__main__":
    asyncio.run(example_usage()) 