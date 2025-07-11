# Basic Pipeline Example

## 概要

この例では、Bunsuiを使用して基本的なデータ処理パイプラインを作成します。

## パイプライン定義

```yaml
# basic-pipeline.yaml
version: "1.0"
name: "Basic Data Pipeline"
description: "A simple data processing pipeline"

parameters:
  - name: input_bucket
    type: string
    required: true
    description: "Input S3 bucket name"
  - name: output_bucket
    type: string
    required: true
    description: "Output S3 bucket name"
  - name: processing_date
    type: string
    required: true
    description: "Processing date (YYYY-MM-DD)"

jobs:
  - id: validate_input
    name: "Validate Input"
    type: lambda
    parameters:
      function_name: "data-validation-function"
      payload:
        bucket: "${input_bucket}"
        date: "${processing_date}"
    
  - id: process_data
    name: "Process Data"
    type: lambda
    parameters:
      function_name: "data-processing-function"
      payload:
        input_bucket: "${input_bucket}"
        output_bucket: "${output_bucket}"
        date: "${processing_date}"
    depends_on: [validate_input]
    
  - id: generate_report
    name: "Generate Report"
    type: lambda
    parameters:
      function_name: "report-generation-function"
      payload:
        output_bucket: "${output_bucket}"
        date: "${processing_date}"
    depends_on: [process_data]

metadata:
  owner: "data-team"
  environment: "development"
  tags:
    - "basic"
    - "data-processing"
```

## 実行手順

### 1. パイプラインの作成

```bash
bunsui pipeline create --file basic-pipeline.yaml
```

### 2. パラメータの設定

```bash
bunsui config set aws.region ap-northeast-1
bunsui config set aws.profile default
```

### 3. セッションの開始

```bash
bunsui session start \
  --pipeline "Basic Data Pipeline" \
  --parameters \
    input_bucket=my-input-bucket \
    output_bucket=my-output-bucket \
    processing_date=2024-01-15
```

### 4. セッションの監視

```bash
# セッションステータスの確認
bunsui session status --session-id <session-id>

# ログの表示
bunsui logs tail --session-id <session-id>

# フィルタリングされたログ
bunsui logs filter --session-id <session-id> --level INFO
```

## 期待される結果

このパイプラインは以下の処理を実行します：

1. **入力検証**: 指定されたS3バケットと日付のデータが存在することを確認
2. **データ処理**: 入力データを処理して出力バケットに保存
3. **レポート生成**: 処理結果のレポートを生成

## トラブルシューティング

### よくある問題

1. **Lambda関数が見つからない**
   ```bash
   # Lambda関数の存在確認
   aws lambda list-functions --query 'Functions[?FunctionName==`data-validation-function`]'
   ```

2. **S3バケットアクセスエラー**
   ```bash
   # バケットの存在確認
   aws s3 ls s3://my-input-bucket/
   ```

3. **IAM権限エラー**
   ```bash
   # 現在のIAMユーザー確認
   aws sts get-caller-identity
   ```

## 拡張例

### エラーハンドリングの追加

```yaml
jobs:
  - id: validate_input
    name: "Validate Input"
    type: lambda
    parameters:
      function_name: "data-validation-function"
      payload:
        bucket: "${input_bucket}"
        date: "${processing_date}"
    retries: 3
    retry_delay: 60
    timeout: 300
```

### 条件付き実行

```yaml
jobs:
  - id: process_data
    name: "Process Data"
    type: lambda
    parameters:
      function_name: "data-processing-function"
      payload:
        input_bucket: "${input_bucket}"
        output_bucket: "${output_bucket}"
        date: "${processing_date}"
    condition: "${enable_processing}"
    depends_on: [validate_input]
```

### 並列実行

```yaml
jobs:
  - id: process_data_1
    name: "Process Data 1"
    type: lambda
    parameters:
      function_name: "data-processing-function-1"
    depends_on: [validate_input]
    
  - id: process_data_2
    name: "Process Data 2"
    type: lambda
    parameters:
      function_name: "data-processing-function-2"
    depends_on: [validate_input]
    
  - id: merge_results
    name: "Merge Results"
    type: lambda
    parameters:
      function_name: "merge-function"
    depends_on: [process_data_1, process_data_2]
```

## ベストプラクティス

1. **パラメータの使用**: ハードコーディングを避け、パラメータを使用
2. **適切な名前付け**: ジョブIDと名前は意味のある名前を使用
3. **依存関係の管理**: ジョブ間の依存関係を明確に定義
4. **エラーハンドリング**: リトライとタイムアウトを適切に設定
5. **ログ出力**: 各ジョブで適切なログを出力
6. **メタデータ**: パイプラインの管理情報をメタデータに記録 