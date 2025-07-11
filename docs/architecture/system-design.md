# Bunsui System Design Document

## Overview

Bunsuiは、AWSサービスと統合されたデータパイプライン管理ツールです。直感的なTUI（Terminal User Interface）を通じて、複雑なデータパイプラインの構築、実行、監視を行うことができます。

## Architecture Philosophy

### Design Principles

1. **Separation of Concerns**: 各コンポーネントは明確な責任を持つ
2. **Modularity**: 疎結合でテスト可能なモジュール設計
3. **Extensibility**: 新しいOperationタイプやサービスの追加が容易
4. **Resilience**: エラーハンドリングとリカバリー機能の充実
5. **Observability**: 包括的なログ記録と監視機能

## System Architecture (C4 Model)

### Context Level

```
┌─────────────────────────────────────────────────────────────────┐
│                          External Context                        │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │    User     │    │   AWS CLI   │    │   AWS Web Console   │ │
│  │             │    │             │    │                     │ │
│  │  Data       │    │  Config &   │    │  Manual Resource    │ │
│  │  Engineer   │    │  Credential │    │  Management         │ │
│  │             │    │  Management │    │                     │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│          │                   │                        │         │
│          │                   │                        │         │
│          v                   v                        v         │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      Bunsui System                         │ │
│  │                                                             │ │
│  │  TUI-based Data Pipeline Management Tool                   │ │
│  │  - Pipeline Creation & Management                          │ │
│  │  - Session Management                                      │ │
│  │  - Real-time Monitoring                                    │ │
│  │  - Error Handling & Recovery                               │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                │                                │
│                                │                                │
│                                v                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      AWS Services                          │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │    Lambda   │  │Step Functions│  │      DynamoDB       │ │ │
│  │  │             │  │             │  │                     │ │ │
│  │  │  Execution  │  │ Orchestration│  │  Session & Metadata │ │ │
│  │  │  Runtime    │  │   Engine     │  │     Storage         │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │     ECS     │  │     S3      │  │     CloudWatch      │ │ │
│  │  │             │  │             │  │                     │ │ │
│  │  │  Container  │  │  Log & Data │  │   Monitoring &      │ │ │
│  │  │  Runtime    │  │   Storage   │  │    Alerting         │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Container Level

```
┌─────────────────────────────────────────────────────────────────┐
│                      Bunsui System                             │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   TUI Layer     │    │   Core Layer    │    │ AWS Layer   │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │ Pipeline  │  │◄──►│  │ Session   │  │◄──►│ │DynamoDB │ │ │
│  │  │ Builder   │  │    │  │ Manager   │  │    │ │ Client  │ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ └─────────┘ │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │ Monitor   │  │◄──►│  │ Pipeline  │  │◄──►│ │   S3    │ │ │
│  │  │Dashboard  │  │    │  │   DAG     │  │    │ │ Client  │ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ └─────────┘ │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │   CLI     │  │◄──►│  │   Error   │  │◄──►│ │  Step   │ │ │
│  │  │Interface  │  │    │  │ Handler   │  │    │ │Functions│ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ │ Client  │ │ │
│  └─────────────────┘    └─────────────────┘    │ └─────────┘ │ │
│                                                │             │ │
│                                                │ ┌─────────┐ │ │
│                                                │ │  AWS    │ │ │
│                                                │ │ Common  │ │ │
│                                                │ │ Client  │ │ │
│                                                │ └─────────┘ │ │
│                                                └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Level - Core Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                        Core Layer                               │
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │     Models      │    │   Managers      │    │ Interfaces  │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │ Session   │  │◄──►│  │ Session   │  │◄──►│ │Storage  │ │ │
│  │  │  Model    │  │    │  │ Manager   │  │    │ │Interface│ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ └─────────┘ │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │ Pipeline  │  │◄──►│  │ Pipeline  │  │◄──►│ │Execution│ │ │
│  │  │  Model    │  │    │  │ Manager   │  │    │ │Interface│ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ └─────────┘ │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │ ┌─────────┐ │ │
│  │  │    Job    │  │◄──►│  │  Error    │  │◄──►│ │Monitor  │ │ │
│  │  │  Model    │  │    │  │ Handler   │  │    │ │Interface│ │ │
│  │  └───────────┘  │    │  └───────────┘  │    │ └─────────┘ │ │
│  │                 │    │                 │    │             │ │
│  │  ┌───────────┐  │    │  ┌───────────┐  │    │             │ │
│  │  │Operation  │  │◄──►│  │Repository │  │    │             │ │
│  │  │  Model    │  │    │  │ Manager   │  │    │             │ │
│  │  └───────────┘  │    │  └───────────┘  │    │             │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

### Primary Data Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    User     │    │    TUI      │    │    Core     │    │     AWS     │
│  Request    │───►│  Interface  │───►│  Business   │───►│  Services   │
│             │    │             │    │   Logic     │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       ▲                  ▲                  ▲                  │
       │                  │                  │                  │
       │                  │                  │                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ User Feedback│    │ UI Update   │    │ State       │    │ Execution   │
│ & Response  │◄───│ & Events    │◄───│ Management  │◄───│ Results     │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Session Management Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Pipeline   │    │  Session    │    │  DynamoDB   │    │   Step      │
│  Definition │───►│  Creation   │───►│  Storage    │───►│ Functions   │
│             │    │             │    │             │    │ Execution   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                                      │
                           │                                      │
                           ▼                                      │
                   ┌─────────────┐    ┌─────────────┐            │
                   │   Session   │    │    S3       │            │
                   │  Lifecycle  │◄───│ Log Storage │◄───────────┘
                   │ Management  │    │             │
                   └─────────────┘    └─────────────┘
```

### Error Handling Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Error     │    │   Error     │    │ Recovery    │    │   Retry     │
│ Detection   │───►│  Analysis   │───►│  Strategy   │───►│  Execution  │
│             │    │             │    │ Determination│    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       ▲                  │                  │                  │
       │                  │                  │                  │
       │                  ▼                  │                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Monitoring  │    │   Error     │    │  Manual     │    │  Success    │
│ & Alerting  │◄───│  Logging    │    │ Intervention│    │  Recovery   │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Key Components

### 1. Session Management

**Purpose**: パイプライン実行の状態管理とライフサイクル制御

**Components**:
- `Session`: セッションの状態とメタデータを管理
- `SessionManager`: セッションの作成、更新、削除を制御
- `SessionRepository`: DynamoDBとの永続化インターフェース

**Key Features**:
- セッション状態遷移の管理
- チェックポイント機能
- セッション復旧機能
- 並行実行セッションの管理

### 2. Pipeline Management

**Purpose**: DAG構造のパイプライン定義と実行管理

**Components**:
- `Pipeline`: DAGとしてのパイプライン定義
- `Job`: ステップファンクションで実行される作業単位
- `Operation`: Lambda/ECSで実行される処理単位
- `DAGManager`: 依存関係の解決と実行順序の決定

**Key Features**:
- DAG構造の定義と検証
- 依存関係の解決
- 並列実行の最適化
- 実行計画の生成

### 3. AWS Service Integration

**Purpose**: AWS各サービスとの統合とAPI操作

**Components**:
- `AWSClient`: boto3のラッパーとエラーハンドリング
- `StepFunctionsClient`: Step Functions操作
- `DynamoDBClient`: DynamoDB操作
- `S3Client`: S3操作

**Key Features**:
- リトライロジック
- エラーハンドリング
- 認証情報管理
- レート制限対応

## Technology Stack

### Core Technologies

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.8+ | - AWS SDK (boto3) の豊富なサポート<br>- データ処理エコシステムの充実<br>- 開発効率の高さ |
| TUI Framework | Textual | - 現代的なTUIフレームワーク<br>- React風の宣言的UI<br>- 豊富なウィジェット |
| Data Validation | Pydantic | - 型安全なデータ検証<br>- 自動的なシリアライゼーション<br>- 設定管理の簡素化 |
| Configuration | PyYAML | - 人間が読みやすい設定形式<br>- 複雑な設定の表現力<br>- 標準的な設定フォーマット |

### AWS Services

| Service | Usage | Rationale |
|---------|--------|-----------|
| Step Functions | Pipeline Orchestration | - ビジュアルなワークフロー<br>- 状態管理の自動化<br>- エラー処理の組み込み |
| Lambda | Operation Execution | - サーバーレス実行<br>- 自動スケーリング<br>- コスト効率 |
| ECS | Container Operations | - 長時間実行タスク<br>- カスタムランタイム<br>- リソース制御 |
| DynamoDB | Session Storage | - 高可用性<br>- 自動スケーリング<br>- 一貫性保証 |
| S3 | Log & Data Storage | - 無制限ストレージ<br>- 耐久性<br>- ライフサイクル管理 |

## Security Considerations

### Authentication & Authorization

1. **AWS Credentials**: IAM roles/policies による最小権限の原則
2. **Session Security**: セッションIDの暗号化と有効期限管理
3. **Data Encryption**: 転送時および保存時の暗号化

### Network Security

1. **VPC Configuration**: プライベートサブネットでのリソース配置
2. **Security Groups**: 必要最小限のポート開放
3. **NAT Gateway**: アウトバウンド通信の制御

### Data Security

1. **S3 Bucket Policies**: 適切なアクセス制御
2. **DynamoDB Encryption**: 保存時暗号化の有効化
3. **CloudTrail**: API呼び出しの監査ログ

## Performance Considerations

### Scalability

1. **Concurrent Sessions**: 並行セッション数の制限と管理
2. **DynamoDB**: 読み取り/書き込み容量の適切な設定
3. **Lambda**: 同時実行数の制限と監視

### Optimization

1. **Caching**: 頻繁にアクセスされるデータのキャッシュ
2. **Batching**: DynamoDB/S3への batch操作
3. **Connection Pooling**: AWS API 呼び出しの最適化

## Monitoring & Observability

### Metrics

1. **Application Metrics**: セッション実行時間、成功率、エラー率
2. **AWS Service Metrics**: Lambda実行時間、DynamoDB使用量
3. **Business Metrics**: パイプライン実行回数、データ処理量

### Logging

1. **Structured Logging**: JSON形式でのログ出力
2. **Log Levels**: 適切なログレベル設定
3. **Centralized Logging**: CloudWatch Logsへの集約

### Alerting

1. **Error Alerts**: 実行エラーの即座通知
2. **Performance Alerts**: 性能低下の早期発見
3. **Cost Alerts**: 予算超過の監視

## Future Extensibility

### Plugin Architecture

1. **Operation Plugins**: 新しい処理タイプの追加
2. **Storage Plugins**: 追加のストレージバックエンド
3. **Notification Plugins**: 通知方法の拡張

### Multi-Cloud Support

1. **Provider Abstraction**: クラウドプロバイダーの抽象化
2. **Configuration Management**: マルチクラウド設定
3. **Deployment Strategies**: 複数クラウドへの展開

---

*Document Version: 1.0*  
*Last Updated: 2024-01-XX*  
*Next Review: 2024-XX-XX* 