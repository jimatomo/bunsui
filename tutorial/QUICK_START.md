# Bunsui クイックスタートガイド

このガイドでは、Bunsuiを使い始めるための最初のステップを説明します。

## 0. 初期セットアップ（推奨）

**新機能！** まず`bunsui init`コマンドで簡単にセットアップを行いましょう：

```bash
# 🚀 シンプルなセットアップ（推奨）
bunsui init setup

# または、用途に応じたセットアップ
bunsui init setup --mode learning      # 学習用（オフラインモード）
bunsui init setup --mode aws           # AWS開発環境用
bunsui init setup --mode production    # 本番環境用

# プロジェクトにサンプルファイルのみ追加
bunsui init setup --samples-only
```

初期化完了後、次のステップガイドが表示されます。

## 1. インストール確認

```bash
# バージョンを確認
bunsui version

# ヘルプを表示
bunsui --help

# 詳細情報を表示
bunsui --verbose version

# 初期化の検証
bunsui init validate
```

## 2. 最初のパイプラインを作成

### 初期化済みの場合（推奨）

`bunsui init setup`を実行している場合、サンプルファイルが利用可能です：

```bash
# 初期化時に作成されたサンプルを使用
bunsui pipeline create --file ~/.bunsui/samples/simple_pipeline.yaml --dry-run
bunsui pipeline create --file ~/.bunsui/samples/sample_pipeline.yaml --dry-run

# または、プロジェクトディレクトリのtutorialフォルダ（--samples-onlyの場合）
cd tutorial
bunsui pipeline create --file simple_pipeline.yaml --dry-run
```

### 手動セットアップの場合

このディレクトリには、以下のサンプルファイルが含まれています：

- `sample_pipeline.yaml` - ETLパイプラインの例
- `simple_pipeline.yaml` - シンプルなパイプラインの例

```bash
# ドライランで確認（実際には作成されません）
bunsui pipeline create --file simple_pipeline.yaml --dry-run

# 名前と説明を指定してドライラン
bunsui pipeline create --file simple_pipeline.yaml --name "My First Pipeline" --description "初めてのパイプライン" --dry-run
```

### 実際にパイプラインを作成

```bash
# シンプルなパイプラインを作成
bunsui pipeline create --file simple_pipeline.yaml --name "My First Pipeline"

# 説明付きで作成
bunsui pipeline create --file sample_pipeline.yaml --name "ETL Pipeline" --description "データ処理用のETLパイプライン"

# JSON形式で出力
bunsui pipeline create --file simple_pipeline.yaml --name "Simple Pipeline" --format json
```

## 3. パイプラインの確認

```bash
# パイプライン一覧を表示（デフォルトはテーブル形式）
bunsui pipeline list

# JSON形式で表示
bunsui pipeline list --format json

# YAML形式で表示  
bunsui pipeline list --format yaml

# アクティブなパイプラインのみ表示
bunsui pipeline list --status active

# 全パイプラインを表示（制限なし）
bunsui pipeline list --all

# 特定のパイプラインの詳細を表示
bunsui pipeline show pipeline-1

# JSON形式でパイプライン詳細を表示
bunsui pipeline show pipeline-1 --format json
```

## 4. パイプラインの実行（セッション）

```bash
# セッションを開始（パイプラインIDは必須）
bunsui session start pipeline-1

# パラメータを指定してセッションを開始
bunsui session start pipeline-1 --parameters env=dev --parameters region=us-east-1

# 完了まで待機（タイムアウト設定も可能）
bunsui session start pipeline-1 --wait --timeout 3600

# JSON形式で結果を出力
bunsui session start pipeline-1 --format json

# セッション一覧を確認
bunsui session list

# 特定のパイプラインのセッションのみ表示
bunsui session list --pipeline pipeline-1

# アクティブなセッションのみ表示
bunsui session list --status running

# セッションのステータスを確認
bunsui session status session-1
```

## 5. セッション制御

```bash
# セッションを一時停止
bunsui session pause session-1

# セッションを再開
bunsui session resume session-1

# セッションをキャンセル
bunsui session cancel session-1
```

## 6. ログの確認

```bash
# セッションのログをリアルタイムで表示
bunsui logs tail session-1

# ログをフィルタリング
bunsui logs filter session-1

# ログのサマリーを表示
bunsui logs summary session-1

# ログをダウンロード
bunsui logs download session-1
```

## 7. 設定管理

```bash
# 現在の設定を表示
bunsui config show

# 設定一覧を表示
bunsui config list

# 設定値を取得
bunsui config get aws.region

# 設定値を設定
bunsui config set aws.region us-west-2

# 設定を検証
bunsui config validate

# 設定をエクスポート
bunsui config export

# 設定をリセット
bunsui config reset
```

## 8. 初期化管理

```bash
# セットアップ状況の確認
bunsui init validate

# 特定項目のみ検証
bunsui init validate --check-config
bunsui init validate --check-aws
bunsui init validate --check-samples

# 設定のリセット
bunsui init reset --config-only    # 設定のみ
bunsui init reset --samples-only   # サンプルファイルのみ
bunsui init reset --force           # 確認なしでリセット
```

## 9. 診断

問題が発生した場合：

```bash
# 診断を実行
bunsui doctor

# AWS接続をチェック
bunsui doctor --check-aws

# 設定をチェック
bunsui doctor --check-config
```

## 10. インタラクティブモード・TUI

```bash
# インタラクティブモードを起動
bunsui interactive

# TUIインターフェースを起動
bunsui tui
```

## 11. グローバルオプション

全てのコマンドで使用可能なオプション：

```bash
# 詳細出力を有効化
bunsui --verbose pipeline list

# 設定ファイルを指定
bunsui --config /path/to/config.yaml pipeline list

# AWSプロファイルを指定
bunsui --profile dev pipeline list

# AWSリージョンを指定
bunsui --region us-west-2 pipeline list

# 複数のオプションを組み合わせ
bunsui --verbose --profile prod --region us-east-1 session start pipeline-1
```

## 初心者向け推奨ワークフロー

### 🌟 最短経路（5分で開始）

```bash
# 1. 初期化（学習用）
bunsui init setup --mode learning

# 2. サンプルでテスト
bunsui pipeline create --file ~/.bunsui/samples/simple_pipeline.yaml --dry-run

# 3. 診断確認
bunsui doctor

# 4. ヘルプ確認
bunsui --help
```

### 🚀 プロジェクト開始

```bash
# 1. プロジェクトディレクトリに移動
cd your-project

# 2. サンプルファイル配置
bunsui init setup --samples-only

# 3. サンプルを参考に独自パイプライン作成
cp tutorial/simple_pipeline.yaml my-pipeline.yaml
# my-pipeline.yamlを編集

# 4. テスト
bunsui pipeline create --file my-pipeline.yaml --dry-run
```

## トラブルシューティング

### 初期化関連のエラー

**`bunsui init setup`でエラーが発生する場合：**

1. **ディレクトリ権限エラー**：
   ```bash
   bunsui init setup --config-dir ~/custom-bunsui
   ```

2. **既存設定の競合**：
   ```bash
   bunsui init setup --force
   ```

3. **AWS認証エラー（開発モード）**：
   ```bash
   # AWS CLIの設定を確認
   aws configure list
   # オフラインモードにフォールバック
   bunsui init setup --mode offline
   ```

### パイプライン定義エラー

パイプライン作成時にエラーが発生する場合：

1. **まずドライランを実行**して構文エラーを確認：
   ```bash
   bunsui pipeline create --file your_pipeline.yaml --dry-run
   ```

2. **YAML構文**を確認。特に以下の点に注意：
   - インデントが正しいか
   - 引用符の使用
   - 必須フィールドが存在するか

3. **パイプライン定義の形式**が正しいか確認：
   - `jobs` 配列内で `job_id` を使用
   - `operations` 配列内で各オペレーションを定義
   - `dependencies` 配列で依存関係を指定

### AWS接続エラー

実際のパイプライン作成やリスト表示でAWSエラーが発生する場合：

```bash
# ResourceNotFoundException が発生する場合
Error: Requested resource not found
```

これは**正常な動作**です。本格的な使用には以下が必要です：

1. **AWS認証情報の設定**：
   ```bash
   aws configure
   # または
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   ```

2. **DynamoDBテーブルの作成**（管理者により事前に作成される）

3. **適切なIAMロール/ポリシー**の設定

### 学習・テスト目的での使用

AWS環境が設定されていない場合でも、以下の機能は利用可能です：

- ✅ パイプライン定義のドライラン検証
- ✅ 設定の確認・変更  
- ✅ ヘルプとドキュメントの確認
- ✅ CLIコマンドの構文確認
- ✅ 初期化とセットアップ機能

実際のパイプライン実行には AWS 環境が必要ですが、パイプライン設計と学習には十分です。

## 次のステップ

1. `TUTORIAL.md` を読んで、より詳細な使い方を学ぶ
2. 実際のAWSリソースと統合する
3. TUIモードを試す: `bunsui tui`
4. インタラクティブモードを試す: `bunsui interactive`
5. 設定ファイルをカスタマイズする
6. チームでの使用方法を検討する

## 注意事項

- このツールは現在開発中のため、一部の機能は実装されていない可能性があります
- 実際のAWSリソースを使用する場合は、適切な認証情報とIAMロールが必要です
- サンプルファイルのAWSリソース（Lambda関数、S3バケットなど）は架空のものです
- コマンドの出力形式は `--format` オプションで `table`、`json`、`yaml` から選択できます
- **推奨**: まず `bunsui init setup` で初期化してからチュートリアルを開始してください
- ドライラン機能を使用してパイプライン定義を検証することを強く推奨します 