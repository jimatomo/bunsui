# Architecture

## 概要

Bunsuiは、AWS連携のデータパイプライン管理ツールです。モジュラー設計により、拡張性と保守性を重視したアーキテクチャを採用しています。

## システムアーキテクチャ

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Layer     │    │  Core Engine    │    │  AWS Services   │
│                 │    │                 │    │                 │
│ • Commands      │◄──►│ • Pipeline      │◄──►│ • Lambda        │
│ • Interactive   │    │ • Session       │    │ • ECS           │
│ • Config        │    │ • Job Executor  │    │ • Step Function │
└─────────────────┘    └─────────────────┘    │ • Glue          │
                                              │ • EMR           │
┌─────────────────┐    ┌─────────────────┐    │ • S3            │
│   DSL Layer     │    │  Auth Layer     │    │ • CloudWatch    │
│                 │    │                 │    └─────────────────┘
│ • Parser        │◄──►│ • IAM Auth      │
│ • Validator     │    │ • RBAC          │
│ • Schema        │    │ • Token Mgr     │
│ • Templating    │    └─────────────────┘
└─────────────────┘
                                              ┌─────────────────┐
                                              │  Monitoring     │
                                              │                 │
                                              │ • Structured    │
                                              │   Logging       │
                                              │ • Metrics       │
                                              │ • Alerts        │
                                              └─────────────────┘
```

## コンポーネント詳細

### 1. CLI Layer

**責任**: ユーザーインターフェース、コマンド処理

**主要コンポーネント**:
- `cli/commands/`: 各コマンドの実装
- `cli/interactive.py`: インタラクティブモード
- `cli/config.py`: 設定管理

**特徴**:
- Clickフレームワークを使用
- プラグイン可能なコマンド構造
- 設定の永続化

### 2. DSL Layer

**責任**: パイプライン定義の解析・検証

**主要コンポーネント**:
- `dsl/parser.py`: YAMLパーサー
- `dsl/validator.py`: バリデーション
- `dsl/schema.py`: スキーマ定義
- `dsl/templating.py`: テンプレート機能

**特徴**:
- YAMLベースのDSL
- 変数展開機能
- テンプレートエンジン（Jinja2）

### 3. Core Engine

**責任**: パイプライン実行、セッション管理

**主要コンポーネント**:
- `core/pipeline.py`: パイプライン管理
- `core/session.py`: セッション管理
- `core/executor.py`: ジョブ実行
- `core/scheduler.py`: スケジューリング

**特徴**:
- 非同期実行
- 依存関係管理
- エラーハンドリング

### 4. Auth Layer

**責任**: 認証・認可

**主要コンポーネント**:
- `auth/authenticator.py`: 認証処理
- `auth/rbac.py`: ロールベースアクセス制御
- `auth/token_manager.py`: トークン管理
- `auth/middleware.py`: 認証ミドルウェア

**特徴**:
- AWS IAM統合
- JWTトークン
- RBAC実装

### 5. Monitoring Layer

**責任**: ログ・メトリクス・アラート

**主要コンポーネント**:
- `logging/structured_logger.py`: 構造化ログ
- `monitoring/metrics.py`: メトリクス収集
- `monitoring/alerts.py`: アラート設定

**特徴**:
- JSON形式ログ
- CloudWatch統合
- カスタムメトリクス

## データフロー

### パイプライン実行フロー

```
1. CLI Command
   ↓
2. DSL Parser (YAML → Pipeline Object)
   ↓
3. Validator (Schema + Business Rules)
   ↓
4. Auth Check (IAM + RBAC)
   ↓
5. Session Creation
   ↓
6. Job Execution (AWS Services)
   ↓
7. Monitoring (Logs + Metrics)
   ↓
8. Result Reporting
```

### 認証フロー

```
1. User Request
   ↓
2. Token Validation
   ↓
3. IAM Policy Check
   ↓
4. RBAC Permission Check
   ↓
5. Resource Access
```

## 技術スタック

### バックエンド
- **Python 3.8+**: メイン言語
- **asyncio**: 非同期処理
- **boto3**: AWS SDK
- **PyYAML**: YAML処理
- **Jinja2**: テンプレートエンジン

### フロントエンド
- **Click**: CLIフレームワーク
- **rich**: ターミナルUI
- **tabulate**: テーブル表示

### テスト・品質
- **pytest**: テストフレームワーク
- **LocalStack**: AWSモック
- **mypy**: 型チェック
- **black**: コードフォーマット

### ドキュメント
- **Sphinx**: ドキュメント生成
- **Myst**: Markdown拡張

## セキュリティ

### 認証・認可
- AWS IAM統合
- JWTトークン認証
- ロールベースアクセス制御（RBAC）
- 最小権限の原則

### データ保護
- 暗号化通信（TLS）
- 機密情報の暗号化
- アクセスログの記録

### 監査
- 操作ログの記録
- セキュリティイベントの監視
- 定期的なセキュリティ監査

## スケーラビリティ

### 水平スケーリング
- ステートレス設計
- 複数インスタンスでの実行
- ロードバランサー対応

### 垂直スケーリング
- リソース使用量の最適化
- メモリ効率の改善
- CPU使用率の監視

### パフォーマンス
- 非同期処理
- キャッシュ機能
- バッチ処理

## 監視・運用

### ログ管理
- 構造化ログ（JSON）
- ログレベル管理
- ログローテーション

### メトリクス
- 実行時間
- 成功率
- エラー率
- リソース使用量

### アラート
- エラー率の閾値
- 実行時間の閾値
- リソース使用量の閾値

## デプロイメント

### 開発環境
- LocalStack
- Docker Compose
- 仮想環境

### 本番環境
- AWS ECS/Fargate
- AWS Lambda
- AWS Step Functions

### CI/CD
- GitHub Actions
- 自動テスト
- 自動デプロイ

## 将来の拡張

### 計画中の機能
- リアルタイムダッシュボード
- 高度なスケジューリング
- マルチクラウド対応
- プラグインシステム

### 技術的改善
- GraphQL API
- WebSocket対応
- マイクロサービス化
- コンテナ化 