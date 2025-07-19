# Bunsui クイックスタートガイド

このガイドでは、Bunsuiを使い始めるための最初のステップを説明します。

## 1. インストール確認

```bash
# バージョンを確認
bunsui version

# ヘルプを表示
bunsui --help

# 詳細情報を表示
bunsui --verbose version
```

## 2. 最初のパイプラインを作成

このディレクトリには、以下のサンプルファイルが含まれています：

- `sample_pipeline.yaml` - ETLパイプラインの例
- `simple_pipeline.yaml` - シンプルなパイプラインの例

### パイプラインを作成する前に確認

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

## 8. 診断

問題が発生した場合：

```bash
# 診断を実行
bunsui doctor

# AWS接続をチェック
bunsui doctor --check-aws

# 設定をチェック
bunsui doctor --check-config
```

## 9. インタラクティブモード・TUI

```bash
# インタラクティブモードを起動
bunsui interactive

# TUIインターフェースを起動
bunsui tui
```

## 10. グローバルオプション

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

## トラブルシューティング

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

実際のパイプライン実行には AWS 環境が必要ですが、パイプライン設計と学習には十分です。

## 次のステップ

1. `TUTORIAL.md` を読んで、より詳細な使い方を学ぶ
2. 実際のAWSリソースと統合する
3. TUIモードを試す: `bunsui tui`
4. インタラクティブモードを試す: `bunsui interactive`
5. 設定ファイルをカスタマイズする

## 注意事項

- このツールは現在開発中のため、一部の機能は実装されていない可能性があります
- 実際のAWSリソースを使用する場合は、適切な認証情報とIAMロールが必要です
- サンプルファイルのAWSリソース（Lambda関数、S3バケットなど）は架空のものです
- コマンドの出力形式は `--format` オプションで `table`、`json`、`yaml` から選択できます
- ドライラン機能を使用してパイプライン定義を検証することを強く推奨します 