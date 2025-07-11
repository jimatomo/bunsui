# ETL Pipeline Example

## 概要

この例では、Bunsuiを使用してETL（Extract, Transform, Load）パイプラインを作成します。データベースからデータを抽出し、変換して、データウェアハウスにロードする処理を実装します。

## パイプライン定義

```yaml
# etl-pipeline.yaml
version: "1.0"
name: "ETL Data Pipeline"
description: "Daily ETL process for data warehouse"

parameters:
  - name: source_database
    type: string
    required: true
    description: "Source database name"
  - name: target_warehouse
    type: string
    required: true
    description: "Target data warehouse name"
  - name: processing_date
    type: string
    required: true
    description: "Processing date (YYYY-MM-DD)"
  - name: batch_size
    type: integer
    default: 10000
    description: "Batch size for processing"
    validation:
      min: 1000
      max: 100000

jobs:
  - id: extract_data
    name: "Extract Data"
    type: lambda
    parameters:
      function_name: "data-extraction-function"
      payload:
        source_database: "${source_database}"
        processing_date: "${processing_date}"
        batch_size: "${batch_size}"
    
  - id: validate_extracted_data
    name: "Validate Extracted Data"
    type: lambda
    parameters:
      function_name: "data-validation-function"
      payload:
        processing_date: "${processing_date}"
    depends_on: [extract_data]
    
  - id: transform_data
    name: "Transform Data"
    type: glue
    parameters:
      job_name: "data-transformation-job"
      arguments:
        --source_path: "s3://raw-data-bucket/${processing_date}"
        --target_path: "s3://processed-data-bucket/${processing_date}"
        --processing_date: "${processing_date}"
    depends_on: [validate_extracted_data]
    timeout: 3600
    
  - id: load_to_warehouse
    name: "Load to Warehouse"
    type: lambda
    parameters:
      function_name: "data-loading-function"
      payload:
        target_warehouse: "${target_warehouse}"
        processed_data_path: "s3://processed-data-bucket/${processing_date}"
        processing_date: "${processing_date}"
    depends_on: [transform_data]
    
  - id: generate_summary
    name: "Generate Summary"
    type: lambda
    parameters:
      function_name: "summary-generation-function"
      payload:
        target_warehouse: "${target_warehouse}"
        processing_date: "${processing_date}"
    depends_on: [load_to_warehouse]

metadata:
  owner: "data-engineering"
  environment: "production"
  schedule: "daily"
  data_retention: "90 days"
  tags:
    - "etl"
    - "data-warehouse"
    - "daily"
```

## 実行手順

### 1. パイプラインの作成

```bash
bunsui pipeline create --file etl-pipeline.yaml
```

### 2. セッションの開始

```bash
bunsui session start \
  --pipeline "ETL Data Pipeline" \
  --parameters \
    source_database=production_db \
    target_warehouse=analytics_warehouse \
    processing_date=2024-01-15 \
    batch_size=50000
```

### 3. セッションの監視

```bash
# セッションステータスの確認
bunsui session status --session-id <session-id>

# リアルタイムログ
bunsui logs tail --session-id <session-id>

# エラーログのみ
bunsui logs filter --session-id <session-id> --level ERROR
```

## ジョブ詳細

### 1. Extract Data

**目的**: ソースデータベースからデータを抽出

**処理内容**:
- 指定日付のデータを抽出
- S3に一時保存
- データ品質チェック

**Lambda関数の例**:
```python
import boto3
import json
import psycopg2
from datetime import datetime

def lambda_handler(event, context):
    # パラメータ取得
    source_db = event['source_database']
    processing_date = event['processing_date']
    batch_size = event['batch_size']
    
    # データベース接続
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=source_db,
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD']
    )
    
    # データ抽出
    query = """
    SELECT * FROM transactions 
    WHERE DATE(created_at) = %s
    ORDER BY created_at
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (processing_date,))
        rows = cur.fetchmany(batch_size)
    
    # S3に保存
    s3 = boto3.client('s3')
    bucket = 'raw-data-bucket'
    key = f'{processing_date}/extracted_data.json'
    
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(rows)
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'extracted_count': len(rows),
            's3_location': f's3://{bucket}/{key}'
        })
    }
```

### 2. Validate Extracted Data

**目的**: 抽出されたデータの品質を検証

**検証項目**:
- データ件数
- 必須フィールドの存在
- データ型の妥当性
- 重複チェック

### 3. Transform Data

**目的**: データの変換・クリーニング

**Glueジョブの例**:
```python
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source_path', 'target_path', 'processing_date'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# データ読み込み
df = spark.read.json(args['source_path'])

# データ変換
transformed_df = df.select(
    col('id'),
    col('amount').cast('decimal(10,2)'),
    col('created_at').cast('timestamp'),
    col('customer_id'),
    upper(col('status')).alias('status'),
    when(col('amount') > 1000, 'high_value')
    .when(col('amount') > 100, 'medium_value')
    .otherwise('low_value').alias('value_category')
).filter(col('amount') > 0)

# データ保存
transformed_df.write.mode('overwrite').parquet(args['target_path'])

job.commit()
```

### 4. Load to Warehouse

**目的**: 変換されたデータをデータウェアハウスにロード

**処理内容**:
- パーティション分割
- インデックス作成
- 統計情報の更新

### 5. Generate Summary

**目的**: 処理結果のサマリーを生成

**出力内容**:
- 処理件数
- 処理時間
- エラー件数
- データ品質指標

## エラーハンドリング

### リトライ設定

```yaml
jobs:
  - id: transform_data
    name: "Transform Data"
    type: glue
    parameters:
      job_name: "data-transformation-job"
    retries: 3
    retry_delay: 300
    timeout: 3600
```

### 条件付き実行

```yaml
jobs:
  - id: load_to_warehouse
    name: "Load to Warehouse"
    type: lambda
    parameters:
      function_name: "data-loading-function"
    condition: "${enable_warehouse_load}"
    depends_on: [transform_data]
```

## 監視・アラート

### CloudWatchメトリクス

```python
import boto3

def record_metrics(processing_date, record_count, duration):
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='Bunsui/ETL',
        MetricData=[
            {
                'MetricName': 'RecordsProcessed',
                'Value': record_count,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ProcessingDate', 'Value': processing_date}
                ]
            },
            {
                'MetricName': 'ProcessingDuration',
                'Value': duration,
                'Unit': 'Seconds',
                'Dimensions': [
                    {'Name': 'ProcessingDate', 'Value': processing_date}
                ]
            }
        ]
    )
```

### アラート設定

```yaml
# CloudWatchアラーム設定例
alarms:
  - name: "ETL-Processing-Errors"
    metric: "Errors"
    threshold: 1
    period: 300
    evaluation_periods: 1
    
  - name: "ETL-Processing-Duration"
    metric: "ProcessingDuration"
    threshold: 3600
    period: 300
    evaluation_periods: 2
```

## パフォーマンス最適化

### 並列処理

```yaml
jobs:
  - id: extract_data_1
    name: "Extract Data - Table 1"
    type: lambda
    parameters:
      function_name: "data-extraction-function"
      payload:
        table: "transactions"
        processing_date: "${processing_date}"
    
  - id: extract_data_2
    name: "Extract Data - Table 2"
    type: lambda
    parameters:
      function_name: "data-extraction-function"
      payload:
        table: "customers"
        processing_date: "${processing_date}"
    
  - id: merge_data
    name: "Merge Data"
    type: glue
    parameters:
      job_name: "data-merging-job"
    depends_on: [extract_data_1, extract_data_2]
```

### パーティション分割

```yaml
jobs:
  - id: transform_data
    name: "Transform Data"
    type: glue
    parameters:
      job_name: "data-transformation-job"
      arguments:
        --source_path: "s3://raw-data-bucket/${processing_date}"
        --target_path: "s3://processed-data-bucket/${processing_date}"
        --partition_by: "customer_id"
        --num_partitions: "10"
```

## ベストプラクティス

1. **データ品質**: 各段階でデータ品質を検証
2. **エラーハンドリング**: 適切なリトライとタイムアウト設定
3. **監視**: 詳細なメトリクスとアラート設定
4. **パフォーマンス**: 並列処理とパーティション分割
5. **セキュリティ**: 適切なIAM権限と暗号化
6. **ドキュメント**: 処理内容と依存関係の明確化 