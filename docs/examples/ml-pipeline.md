# ML Pipeline Example

## 概要

この例では、Bunsuiを使用して機械学習パイプラインを作成します。データ準備からモデル学習、評価、デプロイまでを含む完全なMLワークフローを実装します。

## パイプライン定義

```yaml
# ml-pipeline.yaml
version: "1.0"
name: "ML Training Pipeline"
description: "Machine learning model training pipeline"

parameters:
  - name: model_name
    type: string
    required: true
    description: "Model name"
    validation:
      pattern: "^[a-zA-Z][a-zA-Z0-9_-]*$"
  - name: training_data_path
    type: string
    required: true
    description: "Training data S3 path"
  - name: model_version
    type: string
    default: "v1.0"
    description: "Model version"
  - name: hyperparameters
    type: object
    default: {}
    description: "Model hyperparameters"
  - name: evaluation_threshold
    type: float
    default: 0.8
    description: "Minimum accuracy threshold for deployment"
    validation:
      min: 0.0
      max: 1.0

jobs:
  - id: prepare_data
    name: "Prepare Training Data"
    type: lambda
    parameters:
      function_name: "data-preparation-function"
      payload:
        training_data_path: "${training_data_path}"
        model_name: "${model_name}"
        output_path: "s3://ml-bucket/prepared/${model_name}"
    
  - id: validate_data
    name: "Validate Data Quality"
    type: lambda
    parameters:
      function_name: "data-validation-function"
      payload:
        data_path: "s3://ml-bucket/prepared/${model_name}"
        model_name: "${model_name}"
    depends_on: [prepare_data]
    
  - id: train_model
    name: "Train Model"
    type: ecs
    parameters:
      task_definition: "ml-training-task"
      cluster: "ml-cluster"
      environment:
        MODEL_NAME: "${model_name}"
        DATA_PATH: "s3://ml-bucket/prepared/${model_name}"
        HYPERPARAMETERS: "${hyperparameters}"
        OUTPUT_PATH: "s3://ml-bucket/models/${model_name}/${model_version}"
    depends_on: [validate_data]
    timeout: 7200
    retries: 2
    
  - id: evaluate_model
    name: "Evaluate Model"
    type: lambda
    parameters:
      function_name: "model-evaluation-function"
      payload:
        model_path: "s3://ml-bucket/models/${model_name}/${model_version}"
        test_data_path: "s3://ml-bucket/test/${model_name}"
        threshold: "${evaluation_threshold}"
    depends_on: [train_model]
    
  - id: deploy_model
    name: "Deploy Model"
    type: lambda
    parameters:
      function_name: "model-deployment-function"
      payload:
        model_path: "s3://ml-bucket/models/${model_name}/${model_version}"
        model_name: "${model_name}"
        model_version: "${model_version}"
    depends_on: [evaluate_model]
    condition: "${evaluation_passed}"
    
  - id: update_registry
    name: "Update Model Registry"
    type: lambda
    parameters:
      function_name: "model-registry-function"
      payload:
        model_name: "${model_name}"
        model_version: "${model_version}"
        model_path: "s3://ml-bucket/models/${model_name}/${model_version}"
        metrics: "${evaluation_metrics}"
    depends_on: [deploy_model]

metadata:
  owner: "ml-team"
  environment: "staging"
  model_type: "classification"
  framework: "scikit-learn"
  tags:
    - "ml"
    - "training"
    - "classification"
```

## 実行手順

### 1. パイプラインの作成

```bash
bunsui pipeline create --file ml-pipeline.yaml
```

### 2. セッションの開始

```bash
bunsui session start \
  --pipeline "ML Training Pipeline" \
  --parameters \
    model_name=customer_churn_model \
    training_data_path=s3://data-bucket/customer_data.csv \
    model_version=v1.1 \
    hyperparameters='{"max_depth": 10, "n_estimators": 100}' \
    evaluation_threshold=0.85
```

### 3. セッションの監視

```bash
# セッションステータスの確認
bunsui session status --session-id <session-id>

# リアルタイムログ
bunsui logs tail --session-id <session-id>

# 特定のジョブのログ
bunsui logs filter --session-id <session-id> --job-id train_model
```

## ジョブ詳細

### 1. Prepare Data

**目的**: トレーニングデータの前処理

**処理内容**:
- データクリーニング
- 特徴量エンジニアリング
- データ分割（train/test）

**Lambda関数の例**:
```python
import boto3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import json

def lambda_handler(event, context):
    # パラメータ取得
    training_data_path = event['training_data_path']
    model_name = event['model_name']
    output_path = event['output_path']
    
    # S3からデータ読み込み
    s3 = boto3.client('s3')
    bucket = training_data_path.split('/')[2]
    key = '/'.join(training_data_path.split('/')[3:])
    
    response = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(response['Body'])
    
    # データクリーニング
    df = df.dropna()
    df = df.drop_duplicates()
    
    # 特徴量エンジニアリング
    df['age_group'] = pd.cut(df['age'], bins=[0, 25, 35, 50, 100], labels=['young', 'adult', 'senior', 'elderly'])
    df['total_spent'] = df['monthly_charges'] * df['tenure']
    
    # カテゴリカル変数のエンコーディング
    categorical_cols = ['gender', 'contract_type', 'payment_method']
    df_encoded = pd.get_dummies(df, columns=categorical_cols)
    
    # 特徴量とターゲットの分離
    feature_cols = [col for col in df_encoded.columns if col != 'churn']
    X = df_encoded[feature_cols]
    y = df_encoded['churn']
    
    # データ分割
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # スケーリング
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 処理済みデータをS3に保存
    train_data = {
        'X_train': X_train_scaled.tolist(),
        'y_train': y_train.tolist(),
        'feature_names': feature_cols,
        'scaler_params': scaler.get_params()
    }
    
    test_data = {
        'X_test': X_test_scaled.tolist(),
        'y_test': y_test.tolist()
    }
    
    # S3に保存
    s3.put_object(
        Bucket='ml-bucket',
        Key=f'prepared/{model_name}/train_data.json',
        Body=json.dumps(train_data)
    )
    
    s3.put_object(
        Bucket='ml-bucket',
        Key=f'prepared/{model_name}/test_data.json',
        Body=json.dumps(test_data)
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'features': len(feature_cols)
        })
    }
```

### 2. Validate Data

**目的**: データ品質の検証

**検証項目**:
- データサイズ
- 欠損値
- 異常値
- クラスバランス

### 3. Train Model

**目的**: モデルの学習

**ECSタスク定義の例**:
```json
{
  "family": "ml-training-task",
  "containerDefinitions": [
    {
      "name": "training-container",
      "image": "ml-training:latest",
      "environment": [
        {"name": "MODEL_NAME", "value": "${MODEL_NAME}"},
        {"name": "DATA_PATH", "value": "${DATA_PATH}"},
        {"name": "HYPERPARAMETERS", "value": "${HYPERPARAMETERS}"},
        {"name": "OUTPUT_PATH", "value": "${OUTPUT_PATH}"}
      ],
      "memory": 4096,
      "cpu": 2048
    }
  ]
}
```

**学習スクリプトの例**:
```python
import boto3
import json
import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import os

def train_model():
    # 環境変数からパラメータ取得
    model_name = os.environ['MODEL_NAME']
    data_path = os.environ['DATA_PATH']
    hyperparameters = json.loads(os.environ['HYPERPARAMETERS'])
    output_path = os.environ['OUTPUT_PATH']
    
    # S3からデータ読み込み
    s3 = boto3.client('s3')
    
    # トレーニングデータ読み込み
    response = s3.get_object(Bucket='ml-bucket', Key=f'prepared/{model_name}/train_data.json')
    train_data = json.loads(response['Body'].read())
    
    X_train = np.array(train_data['X_train'])
    y_train = np.array(train_data['y_train'])
    
    # モデル学習
    model = RandomForestClassifier(**hyperparameters, random_state=42)
    model.fit(X_train, y_train)
    
    # テストデータで評価
    response = s3.get_object(Bucket='ml-bucket', Key=f'prepared/{model_name}/test_data.json')
    test_data = json.loads(response['Body'].read())
    
    X_test = np.array(test_data['X_test'])
    y_test = np.array(test_data['y_test'])
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # モデルとメトリクスをS3に保存
    model_data = {
        'model': pickle.dumps(model),
        'accuracy': accuracy,
        'hyperparameters': hyperparameters,
        'feature_names': train_data['feature_names']
    }
    
    s3.put_object(
        Bucket='ml-bucket',
        Key=f'models/{model_name}/model.pkl',
        Body=pickle.dumps(model_data)
    )
    
    # メトリクスをCloudWatchに送信
    cloudwatch = boto3.client('cloudwatch')
    cloudwatch.put_metric_data(
        Namespace='Bunsui/ML',
        MetricData=[
            {
                'MetricName': 'ModelAccuracy',
                'Value': accuracy,
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'ModelName', 'Value': model_name}
                ]
            }
        ]
    )
    
    return accuracy

if __name__ == "__main__":
    accuracy = train_model()
    print(f"Model accuracy: {accuracy:.4f}")
```

### 4. Evaluate Model

**目的**: モデルの評価

**評価指標**:
- 精度（Accuracy）
- 適合率（Precision）
- 再現率（Recall）
- F1スコア
- ROC-AUC

### 5. Deploy Model

**目的**: モデルのデプロイ

**デプロイ方法**:
- Lambda関数としてデプロイ
- SageMakerエンドポイント
- API Gateway + Lambda

### 6. Update Registry

**目的**: モデルレジストリの更新

**更新内容**:
- モデルメタデータ
- バージョン管理
- パフォーマンス履歴

## 条件付き実行

### 評価結果によるデプロイ制御

```yaml
jobs:
  - id: deploy_model
    name: "Deploy Model"
    type: lambda
    parameters:
      function_name: "model-deployment-function"
    condition: "${evaluation_accuracy >= evaluation_threshold}"
    depends_on: [evaluate_model]
```

## 監視・アラート

### MLメトリクス

```python
import boto3

def record_ml_metrics(model_name, accuracy, training_time):
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='Bunsui/ML',
        MetricData=[
            {
                'MetricName': 'ModelAccuracy',
                'Value': accuracy * 100,
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'ModelName', 'Value': model_name}
                ]
            },
            {
                'MetricName': 'TrainingTime',
                'Value': training_time,
                'Unit': 'Seconds',
                'Dimensions': [
                    {'Name': 'ModelName', 'Value': model_name}
                ]
            }
        ]
    )
```

### アラート設定

```yaml
# CloudWatchアラーム設定例
alarms:
  - name: "ML-Model-Accuracy"
    metric: "ModelAccuracy"
    threshold: 80
    period: 300
    evaluation_periods: 1
    
  - name: "ML-Training-Failure"
    metric: "TrainingErrors"
    threshold: 1
    period: 300
    evaluation_periods: 1
```

## パフォーマンス最適化

### 並列処理

```yaml
jobs:
  - id: prepare_data_1
    name: "Prepare Data - Features"
    type: lambda
    parameters:
      function_name: "feature-engineering-function"
    depends_on: [validate_data]
    
  - id: prepare_data_2
    name: "Prepare Data - Labels"
    type: lambda
    parameters:
      function_name: "label-processing-function"
    depends_on: [validate_data]
    
  - id: train_model
    name: "Train Model"
    type: ecs
    parameters:
      task_definition: "ml-training-task"
    depends_on: [prepare_data_1, prepare_data_2]
```

### ハイパーパラメータチューニング

```yaml
jobs:
  - id: hyperparameter_tuning
    name: "Hyperparameter Tuning"
    type: step_function
    parameters:
      state_machine_arn: "arn:aws:states:region:account:stateMachine:hyperparameter-tuning"
      input:
        model_name: "${model_name}"
        parameter_ranges:
          max_depth: [5, 10, 15]
          n_estimators: [50, 100, 200]
    depends_on: [prepare_data]
    
  - id: train_best_model
    name: "Train Best Model"
    type: ecs
    parameters:
      task_definition: "ml-training-task"
      environment:
        HYPERPARAMETERS: "${best_hyperparameters}"
    depends_on: [hyperparameter_tuning]
```

## ベストプラクティス

1. **データ品質**: トレーニング前のデータ品質検証
2. **実験管理**: ハイパーパラメータと結果の記録
3. **モデルバージョニング**: モデルとメタデータの管理
4. **A/Bテスト**: 新モデルの段階的デプロイ
5. **監視**: モデルパフォーマンスの継続的監視
6. **再学習**: 定期的なモデル更新
7. **セキュリティ**: モデルとデータの暗号化
8. **コンプライアンス**: データプライバシーの確保 