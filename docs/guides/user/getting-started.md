# Getting Started

## インストール

```bash
pip install bunsui
```

## 基本的な使用方法

### 1. 設定

```bash
bunsui config set aws.region ap-northeast-1
bunsui config set aws.profile default
```

### 2. パイプラインの作成

```yaml
# pipeline.yaml
version: "1.0"
name: "My First Pipeline"
description: "A simple data processing pipeline"

parameters:
  - name: input_bucket
    type: string
    required: true
    description: "Input S3 bucket"

jobs:
  - id: process_data
    type: lambda
    parameters:
      function_name: "my-processing-function"
      payload:
        bucket: "${input_bucket}"
```

### 3. パイプラインの実行

```bash
bunsui pipeline create --file pipeline.yaml
bunsui session start --pipeline "My First Pipeline" --parameters input_bucket=my-bucket
```

## 次のステップ

- [CLI Reference](cli-reference.md) - コマンドラインインターフェースの詳細
- [DSL Reference](dsl-reference.md) - パイプライン定義言語の詳細
- [Examples](../examples/) - サンプルコード集 