# Bunsui チュートリアル

このチュートリアルでは、Bunsuiの基本的な使い方を学びます。

## 目次

1. [基本的なコマンドの確認](#基本的なコマンドの確認)
2. [パイプラインの作成と管理](#パイプラインの作成と管理)
3. [セッション管理](#セッション管理)
4. [ログの確認](#ログの確認)
5. [設定管理](#設定管理)
6. [インタラクティブモード](#インタラクティブモード)

## 基本的なコマンドの確認

### 1. バージョン確認

まず、Bunsuiが正しくインストールされていることを確認します：

```bash
# バージョンを表示
bunsui version

# 詳細なバージョン情報を表示
bunsui --verbose version
```

### 2. ヘルプの表示

利用可能なコマンドを確認します：

```bash
# メインヘルプ
bunsui --help

# 特定のコマンドのヘルプ
bunsui pipeline --help
```

## パイプラインの作成と管理

### 1. パイプライン一覧の表示

現在のパイプラインを確認します：

```bash
# デフォルトのテーブル形式で表示
bunsui pipeline list

# JSON形式で表示
bunsui pipeline list --format json

# YAML形式で表示
bunsui pipeline list --format yaml

# ステータスでフィルタリング
bunsui pipeline list --status active
```

### 2. パイプラインの作成

サンプルのパイプライン定義ファイルを使用してパイプラインを作成します：

```bash
# パイプラインを作成（ドライラン）
bunsui pipeline create -f sample_pipeline.yaml --dry-run

# 実際にパイプラインを作成
bunsui pipeline create -f sample_pipeline.yaml --name "My ETL Pipeline"

# シンプルなパイプラインを作成
bunsui pipeline create -f simple_pipeline.yaml --name "Simple Pipeline" --description "チュートリアル用のシンプルなパイプライン"
```

### 3. パイプラインの詳細表示

作成したパイプラインの詳細を確認します：

```bash
# パイプラインの詳細を表示
bunsui pipeline show pipeline-1

# JSON形式で詳細を表示
bunsui pipeline show pipeline-1 --format json
```

### 4. パイプラインの更新

パイプラインの情報を更新します：

```bash
# 名前を更新
bunsui pipeline update pipeline-1 --name "更新されたパイプライン"

# 説明を更新
bunsui pipeline update pipeline-1 --description "新しい説明"

# ドライランで確認
bunsui pipeline update pipeline-1 --file updated_pipeline.yaml --dry-run
```

### 5. パイプラインの削除

不要なパイプラインを削除します：

```bash
# 確認付きで削除
bunsui pipeline delete pipeline-2

# 強制削除（確認なし）
bunsui pipeline delete pipeline-2 --force
```

## セッション管理

### 1. セッション一覧の表示

```bash
# セッション一覧を表示
bunsui session list

# 特定のパイプラインのセッションを表示
bunsui session list --pipeline pipeline-1

# 実行中のセッションのみ表示
bunsui session list --status running
```

### 2. セッションの開始

```bash
# 新しいセッションを開始
bunsui session start pipeline-1

# パラメータを指定してセッションを開始
bunsui session start pipeline-1 --params '{"key": "value"}'
```

### 3. セッションの停止

```bash
# セッションを停止
bunsui session stop session-123

# 強制停止
bunsui session stop session-123 --force
```

## ログの確認

### 1. ログの表示

```bash
# パイプラインのログを表示
bunsui logs show --pipeline pipeline-1

# セッションのログを表示
bunsui logs show --session session-123

# リアルタイムでログを追跡
bunsui logs show --pipeline pipeline-1 --follow

# 直近のログのみ表示
bunsui logs show --pipeline pipeline-1 --tail 50
```

### 2. ログのフィルタリング

```bash
# エラーログのみ表示
bunsui logs show --pipeline pipeline-1 --level ERROR

# 時間範囲を指定
bunsui logs show --pipeline pipeline-1 --since "2024-01-01" --until "2024-01-31"
```

## 設定管理

### 1. 設定の表示

```bash
# 現在の設定を表示
bunsui config show

# 特定の設定項目を表示
bunsui config get aws.region
```

### 2. 設定の変更

```bash
# AWS リージョンを設定
bunsui config set aws.region ap-northeast-1

# プロファイルを設定
bunsui config set aws.profile my-profile
```

### 3. 設定の初期化

```bash
# 対話的に設定を初期化
bunsui config init
```

## インタラクティブモード

Bunsuiはインタラクティブモードもサポートしています：

```bash
# インタラクティブモードを起動
bunsui interactive
```

インタラクティブモードでは、コマンドを対話的に実行できます。

## TUIモード

TUI（Terminal User Interface）モードも利用可能です：

```bash
# TUIモードを起動
bunsui tui
```

注意: TUIモードは現在開発中です。

## 診断とトラブルシューティング

問題が発生した場合は、診断コマンドを使用します：

```bash
# すべての診断を実行
bunsui doctor

# AWS接続をチェック
bunsui doctor --check-aws

# 設定をチェック
bunsui doctor --check-config
```

## パイプライン定義ファイルの例

### sample_pipeline.yaml

このファイルは、ETLパイプラインの定義例です：

- **extract-job**: S3からCSVファイルを読み取る
- **transform-job**: データのクレンジングと変換を実行
- **load-job**: 変換されたデータをS3に保存

### simple_pipeline.yaml

このファイルは、シンプルなパイプラインの定義例です：

- **hello-world**: 最初のサンプルジョブ
- **process-data**: 簡単なデータ処理を実行

## 次のステップ

1. 実際のAWSリソースを使用する場合は、適切なIAMロールとポリシーを設定してください
2. より複雑なパイプラインを作成して、依存関係やエラーハンドリングを試してみてください
3. TUIモードで視覚的にパイプラインを管理してみてください

## トラブルシューティング

### よくある問題

1. **AWS認証エラー**
   - AWS CLIが設定されていることを確認してください
   - 適切なIAMロールが割り当てられていることを確認してください

2. **パイプライン作成エラー**
   - YAMLファイルの構文が正しいことを確認してください
   - 必須フィールドがすべて含まれていることを確認してください

3. **接続エラー**
   - ネットワーク接続を確認してください
   - AWSリージョンが正しく設定されていることを確認してください

## まとめ

このチュートリアルでは、Bunsuiの基本的な使い方を学びました。実際の環境では、AWSリソースとの統合や、より複雑なパイプラインの作成が可能です。詳細については、プロジェクトのドキュメントを参照してください。 