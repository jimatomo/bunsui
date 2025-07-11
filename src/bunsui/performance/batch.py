"""
バッチ処理システム

大量のデータを効率的に処理するためのバッチ処理機能を提供します。
"""

import asyncio
import time
from typing import Callable, List, TypeVar, Generic, Union, Awaitable, cast
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class BatchResult(Generic[T, R]):
    """バッチ処理結果"""
    input_items: List[T]
    output_items: List[R]
    processing_time: float
    success_count: int
    error_count: int
    errors: List[Exception]


class BatchProcessor(Generic[T, R]):
    """バッチプロセッサー"""

    def __init__(
        self,
        processor: Callable[[T], Union[R, Awaitable[R]]],
        batch_size: int = 100,
        max_concurrent: int = 5,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        self.processor = processor
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(self, items: List[T]) -> BatchResult[T, R]:
        """バッチ処理を実行"""
        start_time = time.time()
        output_items = []
        errors = []
        success_count = 0
        error_count = 0

        # バッチに分割
        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        
        # 並行処理
        tasks = []
        for batch in batches:
            task = asyncio.create_task(self._process_single_batch(batch))
            tasks.append(task)

        # 結果を収集
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                errors.append(result)
                error_count += 1
            elif isinstance(result, BatchResult):
                output_items.extend(result.output_items)
                errors.extend(result.errors)
                success_count += result.success_count
                error_count += result.error_count

        processing_time = time.time() - start_time
        
        return BatchResult(
            input_items=items,
            output_items=output_items,
            processing_time=processing_time,
            success_count=success_count,
            error_count=error_count,
            errors=errors
        )

    async def _process_single_batch(self, batch: List[T]) -> BatchResult[T, R]:
        """単一バッチを処理"""
        async with self.semaphore:
            output_items = []
            errors = []
            success_count = 0
            error_count = 0

            for item in batch:
                try:
                    result = await self._process_with_retry(item)
                    output_items.append(result)
                    success_count += 1
                except Exception as e:
                    errors.append(e)
                    error_count += 1
                    logger.error(f"Error processing item: {e}")

            return BatchResult(
                input_items=batch,
                output_items=output_items,
                processing_time=0,  # 個別バッチの時間は記録しない
                success_count=success_count,
                error_count=error_count,
                errors=errors
            )

    async def _process_with_retry(self, item: T) -> R:
        """リトライ付きでアイテムを処理"""
        import inspect
        last_exception = None
        
        for attempt in range(self.retry_count):
            try:
                result = self.processor(item)
                if inspect.isawaitable(result):
                    result = await result
                return cast(R, result)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 指数バックオフ
                    continue
        
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Unknown error in _process_with_retry")


class AsyncBatchProcessor(Generic[T, R]):
    """非同期バッチプロセッサー"""

    def __init__(
        self,
        processor: Callable[[T], R],
        batch_size: int = 100,
        max_concurrent: int = 5,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        self.processor = processor
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(self, items: List[T]) -> BatchResult[T, R]:
        """バッチ処理を実行"""
        start_time = time.time()
        output_items = []
        errors = []
        success_count = 0
        error_count = 0

        # バッチに分割
        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        
        # 並行処理
        tasks = []
        for batch in batches:
            task = asyncio.create_task(self._process_single_batch(batch))
            tasks.append(task)

        # 結果を収集
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in batch_results:
            if isinstance(result, Exception):
                errors.append(result)
                error_count += 1
            elif isinstance(result, BatchResult):
                output_items.extend(result.output_items)
                errors.extend(result.errors)
                success_count += result.success_count
                error_count += result.error_count

        processing_time = time.time() - start_time
        
        return BatchResult(
            input_items=items,
            output_items=output_items,
            processing_time=processing_time,
            success_count=success_count,
            error_count=error_count,
            errors=errors
        )

    async def _process_single_batch(self, batch: List[T]) -> BatchResult[T, R]:
        """単一バッチを処理"""
        async with self.semaphore:
            output_items = []
            errors = []
            success_count = 0
            error_count = 0

            # バッチ内のアイテムを並行処理
            tasks = []
            for item in batch:
                task = asyncio.create_task(self._process_with_retry(item))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    errors.append(result)
                    error_count += 1
                else:
                    output_items.append(result)
                    success_count += 1

            return BatchResult(
                input_items=batch,
                output_items=output_items,
                processing_time=0,
                success_count=success_count,
                error_count=error_count,
                errors=errors
            )

    async def _process_with_retry(self, item: T) -> R:
        """リトライ付きでアイテムを処理"""
        last_exception = None
        
        for attempt in range(self.retry_count):
            try:
                result = self.processor(item)
                if asyncio.iscoroutine(result):
                    return await result
                else:
                    return result
            except Exception as e:
                last_exception = e
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Unknown error in _process_with_retry")


class BatchProcessorFactory:
    """バッチプロセッサーファクトリー"""

    @staticmethod
    def create_sync_processor(
        processor: Callable[[T], R],
        batch_size: int = 100,
        max_concurrent: int = 5,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ) -> BatchProcessor[T, R]:
        """同期プロセッサーを作成"""
        return BatchProcessor(
            processor=processor,
            batch_size=batch_size,
            max_concurrent=max_concurrent,
            retry_count=retry_count,
            retry_delay=retry_delay
        )

    @staticmethod
    def create_async_processor(
        processor: Callable[[T], R],
        batch_size: int = 100,
        max_concurrent: int = 5,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ) -> AsyncBatchProcessor[T, R]:
        """非同期プロセッサーを作成"""
        return AsyncBatchProcessor(
            processor=processor,
            batch_size=batch_size,
            max_concurrent=max_concurrent,
            retry_count=retry_count,
            retry_delay=retry_delay
        )


# 使用例
async def example_usage():
    """使用例"""
    
    # 同期プロセッサーの例
    def sync_processor(item: int) -> str:
        return f"processed_{item}"
    
    sync_batch_processor = BatchProcessorFactory.create_sync_processor(
        processor=sync_processor,
        batch_size=10,
        max_concurrent=3
    )
    
    items = list(range(100))
    result = await sync_batch_processor.process_batch(items)
    
    print(f"Processed {len(result.output_items)} items")
    print(f"Success: {result.success_count}, Errors: {result.error_count}")
    print(f"Processing time: {result.processing_time:.2f}s")
    
    # 非同期プロセッサーの例
    async def async_processor(item: int) -> str:
        await asyncio.sleep(0.1)  # 非同期処理をシミュレート
        return f"async_processed_{item}"
    
    async_batch_processor = BatchProcessorFactory.create_async_processor(
        processor=async_processor,
        batch_size=10,
        max_concurrent=3
    )
    
    result = await async_batch_processor.process_batch(items)
    
    print(f"Async processed {len(result.output_items)} items")
    print(f"Success: {result.success_count}, Errors: {result.error_count}")
    print(f"Processing time: {result.processing_time:.2f}s")


if __name__ == "__main__":
    asyncio.run(example_usage()) 