# DSL Reference

## 概要

Bunsui DSL（Domain Specific Language）は、パイプラインを定義するためのYAMLベースの言語です。

## 基本構造

```yaml
version: "1.0"
name: "Pipeline Name"
description: "Pipeline description"

parameters:
  - name: param_name
    type: string
    required: true
    description: "Parameter description"

jobs:
  - id: job_id
    name: "Job Name"
    type: lambda
    parameters:
      function_name: "function-name"
    depends_on: [other_job_id]
```

## フィールド詳細

### トップレベルフィールド

#### `version`
- **型**: string
- **必須**: はい
- **説明**: パイプライン定義のバージョン
- **有効値**: "1.0", "1.1"

#### `name`
- **型**: string
- **必須**: はい
- **説明**: パイプライン名
- **パターン**: `^[a-zA-Z][a-zA-Z0-9_-]*$`

#### `description`
- **型**: string
- **必須**: いいえ
- **説明**: パイプラインの説明

#### `parameters`
- **型**: array
- **必須**: いいえ
- **説明**: パイプラインパラメータのリスト

#### `jobs`
- **型**: array
- **必須**: はい
- **説明**: ジョブのリスト

#### `metadata`
- **型**: object
- **必須**: いいえ
- **説明**: メタデータ

### パラメータ定義

```yaml
parameters:
  - name: input_bucket
    type: string
    required: true
    description: "Input S3 bucket"
    default: "my-bucket"
    validation:
      pattern: "^[a-z0-9-]+$"
      min: 3
      max: 63
```

#### パラメータフィールド

- **name**: パラメータ名（必須）
- **type**: データ型（string, integer, float, boolean, array, object）
- **required**: 必須フラグ（デフォルト: false）
- **description**: 説明
- **default**: デフォルト値
- **validation**: バリデーションルール

### ジョブ定義

```yaml
jobs:
  - id: process_data
    name: "Process Data"
    type: lambda
    parameters:
      function_name: "my-function"
      payload:
        bucket: "${input_bucket}"
    depends_on: [validate_input]
    timeout: 300
    retries: 3
    retry_delay: 60
    condition: "${enable_processing}"
```

#### ジョブフィールド

- **id**: ジョブID（必須）
- **name**: ジョブ名
- **type**: ジョブタイプ（必須）
- **parameters**: ジョブパラメータ
- **depends_on**: 依存ジョブのリスト
- **timeout**: タイムアウト（秒）
- **retries**: リトライ回数
- **retry_delay**: リトライ間隔（秒）
- **condition**: 実行条件

## ジョブタイプ

### Lambda

```yaml
- id: lambda_job
  type: lambda
  parameters:
    function_name: "my-lambda-function"
    payload:
      key: "value"
```

**必須パラメータ:**
- `function_name`: Lambda関数名

**オプションパラメータ:**
- `payload`: 関数に渡すペイロード

### ECS

```yaml
- id: ecs_job
  type: ecs
  parameters:
    task_definition: "my-task-definition"
    cluster: "my-cluster"
```

**必須パラメータ:**
- `task_definition`: ECSタスク定義名

**オプションパラメータ:**
- `cluster`: ECSクラスター名

### Step Function

```yaml
- id: step_function_job
  type: step_function
  parameters:
    state_machine_arn: "arn:aws:states:region:account:stateMachine:name"
    input:
      key: "value"
```

**必須パラメータ:**
- `state_machine_arn`: Step FunctionのARN

**オプションパラメータ:**
- `input`: ステートマシンへの入力

### Glue

```yaml
- id: glue_job
  type: glue
  parameters:
    job_name: "my-glue-job"
    arguments:
      --source_path: "s3://bucket/path"
      --target_path: "s3://bucket/output"
```

**必須パラメータ:**
- `job_name`: Glueジョブ名

**オプションパラメータ:**
- `arguments`: ジョブ引数

### EMR

```yaml
- id: emr_job
  type: emr
  parameters:
    cluster_id: "j-XXXXXXXXX"
    step_config:
      Name: "My Step"
      ActionOnFailure: "CONTINUE"
      HadoopJarStep:
        Jar: "command-runner.jar"
        Args: ["spark-submit", "s3://bucket/script.py"]
```

**必須パラメータ:**
- `cluster_id`: EMRクラスターID

**オプションパラメータ:**
- `step_config`: EMRステップ設定

### Custom

```yaml
- id: custom_job
  type: custom
  parameters:
    command: "python /path/to/script.py"
    environment:
      ENV_VAR: "value"
```

**必須パラメータ:**
- `command`: 実行コマンド

**オプションパラメータ:**
- `environment`: 環境変数

## 変数展開

パラメータ値やジョブパラメータで変数を展開できます。

```yaml
parameters:
  - name: source_bucket
    type: string
    required: true

jobs:
  - id: process_data
    type: lambda
    parameters:
      function_name: "my-function"
      payload:
        bucket: "${source_bucket}"
        path: "s3://${source_bucket}/data"
```

## バリデーション

パラメータにバリデーションルールを設定できます。

```yaml
parameters:
  - name: batch_size
    type: integer
    validation:
      min: 1
      max: 1000
  - name: email
    type: string
    validation:
      pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
  - name: environment
    type: string
    validation:
      enum: ["dev", "staging", "prod"]
```

## テンプレート機能

Jinja2テンプレートエンジンを使用して動的なパイプライン定義を作成できます。

```yaml
version: "1.0"
name: "{{ pipeline_name }}"
description: "{{ description }}"

parameters:
  - name: input_path
    type: string
    required: true

jobs:
  - id: process_data
    type: lambda
    parameters:
      function_name: "{{ function_name }}"
      payload:
        input_path: "{{ input_path }}"
```

## エラーハンドリング

DSLパーサーは以下のエラーを検出します：

- 必須フィールドの欠如
- 無効なジョブタイプ
- 循環依存
- 存在しないジョブへの依存
- バリデーションエラー
- 構文エラー 