# bunsui 開発ドキュメント

## プロジェクト概要

**bunsui**（分水）は、AWS Step Functions、Lambda、ECS on Fargateを活用したデータパイプラインのオーケストレーションを管理するTUIツールです。AIと人間が協調してデータパイプラインを監視・管理・復旧できる次世代のデータオーケストレーションプラットフォームを目指しています。

### 名前の由来
「分水」は水の流れを分けて制御する仕組みから名付けました。データの流れ（パイプライン）を適切に制御・分配する本ツールの特性を表現しています。

## 主要機能

### 🎯 コア機能
- **TUIダッシュボード**: Textualベースの軽量で高速なターミナルUI
- **セッション管理**: パイプライン実行の状態を一元管理
- **スマートリラン**: 失敗したジョブから効率的に再実行
- **メタデータ管理**: S3/DynamoDBを活用した実行履歴とログの永続化

### 🤖 AI統合機能  
- **AIフレンドリーCLI**: 構造化された出力でAIとの連携を容易に
- **自動エラー分析**: エラーパターンの学習と原因分析
- **復旧提案**: 過去の成功パターンに基づく復旧計画の自動生成
- **協調的運用**: 人間の承認を得ながらAIが運用タスクを実行

### 🏗️ Infrastructure as Code
- **Pythonベースの定義**: CloudFormationテンプレートの自動生成
- **標準コンポーネント**: 再利用可能なリソーステンプレート
- **セキュアな設定**: IAMポリシーの自動生成と最小権限の原則

## アーキテクチャ

### システム構成
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Human     │     │ AI Agent    │     │   bunsui    │
│  Operator   │────▶│  (CLI)      │────▶│    TUI      │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┴───────────────┐
                    │                                          │
              ┌─────▼─────┐  ┌──────────┐  ┌─────────────┐   │
              │   boto3   │  │ DynamoDB │  │     S3      │   │
              │  Wrapper  │──▶│ (State)  │  │   (Logs)    │   │
              └─────┬─────┘  └──────────┘  └─────────────┘   │
                    │                                          │
        ┌───────────┴──────────┬────────────┬─────────────┐  │
        │                      │            │             │  │
   ┌────▼─────┐      ┌────────▼───┐  ┌────▼────┐  ┌─────▼───┐
   │  Step    │      │   Lambda   │  │   ECS   │  │ Event   │
   │Functions │      │            │  │ Fargate │  │ Bridge  │
   └──────────┘      └────────────┘  └─────────┘  └─────────┘
```

### データモデル
- **Pipeline**: DAG構造で定義されたジョブの集合
- **Job**: Step Functionsのステートマシン単位
- **Operation**: Lambda/ECSで実行される処理単位
- **Session**: パイプライン実行の管理単位

## 開発ロードマップ

### 📅 フェーズ別計画
1. **Phase 1** (4週間): コアモジュール開発
2. **Phase 2** (4週間): TUI/CLI実装
3. **Phase 3** (3週間): IaC機能
4. **Phase 4** (4週間): AI統合
5. **Phase 5** (3週間): レポート・高度な機能
6. **Phase 6** (3週間): 本番環境対応

詳細は[開発ロードマップ](./roadmap/bunsui-roadmap.md)を参照してください。

## ドキュメント構成

```
dev_note/
├── README.md              # このファイル
├── roadmap/              # 開発ロードマップ
│   └── bunsui-roadmap.md
├── tasks/                # タスク管理
│   ├── task-template.md
│   └── phase1-core-development.md
├── design/               # 設計ドキュメント
│   └── ai-integration-design.md
└── architecture/         # アーキテクチャ文書
    └── (今後追加予定)
```

## 技術スタック

### 言語・フレームワーク
- **Python 3.11+**: メイン開発言語
- **Textual**: TUIフレームワーク
- **boto3**: AWS SDK
- **Click/Typer**: CLIフレームワーク

### AWS サービス
- **Step Functions**: ワークフローオーケストレーション
- **Lambda**: サーバーレス処理
- **ECS on Fargate**: コンテナ実行環境
- **DynamoDB**: 状態管理
- **S3**: ログ・レポート保存
- **EventBridge Scheduler**: スケジューリング
- **CloudFormation**: IaC

## 開発チーム向け情報

### セットアップ
```bash
# 開発環境のセットアップ
git clone https://github.com/your-org/bunsui
cd bunsui
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.dev.txt
```

### テスト実行
```bash
# ユニットテスト
pytest tests/

# 統合テスト（LocalStack使用）
docker-compose up -d localstack
pytest tests/integration/

# カバレッジレポート
pytest --cov=bunsui tests/
```

### コーディング規約
- Black/isortによる自動フォーマット
- mypyによる型チェック
- pylintによる静的解析
- pre-commitフックの利用

## コントリビューション

1. Issueの作成または既存Issueの選択
2. ブランチの作成: `feature/ISSUE-番号-簡潔な説明`
3. 実装とテストの追加
4. Pull Requestの作成
5. コードレビューと修正
6. マージ

## ライセンス

[ライセンスタイプを選択してください]

## お問い合わせ

- プロジェクトリーダー: [名前] <email@example.com>
- 技術的な質問: [Slackチャンネル/Discord]
- バグ報告: [GitHubのIssue]

---

*"データの流れを制御し、AIと人間の協調を実現する"*

