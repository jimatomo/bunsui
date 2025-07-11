# パフォーマンス最適化ガイド

bunsuiのパフォーマンス最適化機能について説明します。

## 概要

bunsuiは以下のパフォーマンス最適化機能を提供します：

- **キャッシュシステム**: メモリとRedisベースのキャッシュ
- **バッチ処理**: 大量データの効率的な処理
- **接続プーリング**: AWSサービス接続の最適化
- **プロファイリング**: パフォーマンス分析と監視

## キャッシュシステム

### 基本的な使用方法

```python
from bunsui.performance import get_cache_manager, cached

# キャッシュマネージャーを取得
cache_manager = get_cache_manager()

# 値を設定
await cache_manager.set("key", "value", ttl=3600)

# 値を取得
value = await cache_manager.get("key")

# キャッシュデコレータを使用
@cached(ttl=60)
async def expensive_function(param):
    # 重い処理
    return result
```

### キャッシュバックエンド

#### メモリキャッシュ（デフォルト）

```python
from bunsui.performance import MemoryCacheBackend, CacheManager

backend = MemoryCacheBackend(max_size=1000)
cache_manager = CacheManager(backend)
```

#### Redisキャッシュ

```python
from bunsui.performance import RedisCacheBackend, CacheManager

backend = RedisCacheBackend(redis_url="redis://localhost:6379")
cache_manager = CacheManager(backend)
```

### キャッシュ統計

```python
# 統計を取得
stats = cache_manager.get_stats()
print(f"Hit rate: {stats['hit_rate']:.2%}")
print(f"Total requests: {stats['total_requests']}")
```

## バッチ処理

### 同期バッチ処理

```python
from bunsui.performance import BatchProcessorFactory

def process_item(item):
    # アイテム処理
    return processed_item

# バッチプロセッサーを作成
batch_processor = BatchProcessorFactory.create_sync_processor(
    processor=process_item,
    batch_size=100,
    max_concurrent=5
)

# バッチ処理を実行
items = [1, 2, 3, 4, 5]
result = await batch_processor.process_batch(items)

print(f"Processed: {result.success_count}")
print(f"Errors: {result.error_count}")
print(f"Time: {result.processing_time:.2f}s")
```

### 非同期バッチ処理

```python
async def async_process_item(item):
    # 非同期アイテム処理
    await asyncio.sleep(0.1)
    return processed_item

# 非同期バッチプロセッサーを作成
async_batch_processor = BatchProcessorFactory.create_async_processor(
    processor=async_process_item,
    batch_size=50,
    max_concurrent=3
)

# バッチ処理を実行
result = await async_batch_processor.process_batch(items)
```

### エラーハンドリング

```python
def robust_processor(item):
    try:
        return process_item(item)
    except Exception as e:
        logger.error(f"Error processing item {item}: {e}")
        raise

batch_processor = BatchProcessorFactory.create_sync_processor(
    processor=robust_processor,
    retry_count=3,
    retry_delay=1.0
)
```

## 接続プーリング

### AWS接続プール

```python
from bunsui.performance import get_aws_connection_pool

# AWS接続プールを取得
pool = get_aws_connection_pool()

# S3クライアントプールを登録
def create_s3_client():
    import boto3
    return boto3.client('s3')

pool.register_service('s3', create_s3_client, min_size=3, max_size=10)

# プールを開始
await pool.start()

try:
    # S3接続を使用
    async with pool.get_service_connection('s3') as s3_client:
        response = s3_client.list_buckets()
        print(f"Found {len(response['Buckets'])} buckets")
finally:
    # プールを停止
    await pool.stop()
```

### カスタム接続プール

```python
from bunsui.performance import ConnectionPool

def create_database_connection():
    # データベース接続を作成
    return connection

pool = ConnectionPool(
    factory=create_database_connection,
    min_size=5,
    max_size=20,
    max_age=300,
    max_idle=60
)

await pool.start()

try:
    async with pool.get_connection() as conn:
        # データベース操作
        pass
finally:
    await pool.stop()
```

## プロファイリング

### 基本的なプロファイリング

```python
from bunsui.performance import get_performance_monitor, profile_function

monitor = get_performance_monitor()

# モニタリングを開始
monitor.start_monitoring()

try:
    # プロファイリング対象の関数
    @monitor.profile_function
    def slow_function():
        time.sleep(0.1)
        return "result"
    
    # 関数を実行
    result = slow_function()
    
    # 統計を取得
    stats = monitor.get_stats()
    print("Performance stats:", stats)
    
finally:
    # モニタリングを停止
    monitor.stop_monitoring()
```

### コンテキストプロファイリング

```python
async with monitor.profile_context("batch_processing"):
    # バッチ処理を実行
    for item in items:
        await process_item(item)
```

### プロファイルデータのエクスポート

```python
# データをJSONファイルにエクスポート
monitor.export_data("performance_data.json")
```

## 最適化のベストプラクティス

### 1. キャッシュ戦略

```python
# 適切なTTLを設定
@cached(ttl=3600)  # 1時間
async def get_user_profile(user_id):
    # ユーザープロファイル取得
    pass

# パターン無効化
await cache_manager.invalidate_pattern("user_profile:*")
```

### 2. バッチサイズの最適化

```python
# データサイズに応じてバッチサイズを調整
if len(items) > 10000:
    batch_size = 500
else:
    batch_size = 100

batch_processor = BatchProcessorFactory.create_async_processor(
    processor=process_item,
    batch_size=batch_size,
    max_concurrent=min(10, len(items) // batch_size)
)
```

### 3. 接続プールの設定

```python
# サービス特性に応じてプールサイズを設定
pool.register_service('s3', create_s3_client, min_size=5, max_size=20)
pool.register_service('lambda', create_lambda_client, min_size=2, max_size=10)
pool.register_service('dynamodb', create_dynamodb_client, min_size=3, max_size=15)
```

### 4. プロファイリングの活用

```python
# 定期的にパフォーマンスを監視
@profile_function
async def critical_function():
    # 重要な処理
    pass

# パフォーマンスボトルネックを特定
async with monitor.profile_context("data_processing"):
    # データ処理
    pass
```

## パフォーマンス監視

### メトリクス収集

```python
# キャッシュ統計
cache_stats = cache_manager.get_stats()
print(f"Cache hit rate: {cache_stats['hit_rate']:.2%}")

# バッチ処理統計
batch_stats = result
print(f"Batch success rate: {batch_stats.success_count / len(batch_stats.input_items):.2%}")

# 接続プール統計
pool_stats = pool.get_all_stats()
for service, stats in pool_stats.items():
    print(f"{service}: {stats['pool_size']} connections")
```

### アラート設定

```python
# パフォーマンス閾値チェック
def check_performance():
    cache_stats = cache_manager.get_stats()
    
    if cache_stats['hit_rate'] < 0.8:
        logger.warning("Cache hit rate is low")
    
    if batch_stats.error_count > batch_stats.success_count * 0.1:
        logger.error("Batch processing error rate is high")
```

## トラブルシューティング

### よくある問題

1. **キャッシュヒット率が低い**
   - TTLの調整
   - キャッシュキーの最適化
   - キャッシュサイズの増加

2. **バッチ処理が遅い**
   - バッチサイズの調整
   - 並行度の増加
   - プロセッサー関数の最適化

3. **接続プールエラー**
   - プールサイズの調整
   - 接続タイムアウトの設定
   - エラーハンドリングの改善

### デバッグ方法

```python
# 詳細なログを有効化
import logging
logging.getLogger('bunsui.performance').setLevel(logging.DEBUG)

# プロファイリングデータを分析
monitor.export_data("debug_data.json")
```

## まとめ

bunsuiのパフォーマンス最適化機能を活用することで、以下の効果が期待できます：

- **レスポンス時間の短縮**: キャッシュによる高速化
- **スループットの向上**: バッチ処理による効率化
- **リソース使用量の削減**: 接続プールによる最適化
- **ボトルネックの特定**: プロファイリングによる分析

適切な設定と監視により、本番環境での安定したパフォーマンスを実現できます。 