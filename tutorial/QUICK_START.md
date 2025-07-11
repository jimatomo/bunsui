# Bunsui クイックスタートガイド

このガイドでは、Bunsuiを使い始めるための最初のステップを説明します。

## 1. インストール確認

```bash
# バージョンを確認
bunsui version

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
bunsui pipeline create -f simple_pipeline.yaml --dry-run
```

### 実際にパイプラインを作成

```bash
# シンプルなパイプラインを作成
bunsui pipeline create -f simple_pipeline.yaml --name "My First Pipeline"
```

## 3. パイプラインの確認

```bash
# パイプライン一覧を表示
bunsui pipeline list

# 特定のパイプラインの詳細を表示
bunsui pipeline show pipeline-1
```

## 4. パイプラインの実行（セッション）

```bash
# セッションを開始（実際のAWSリソースが設定されていない場合はエラーになる可能性があります）
bunsui session start pipeline-1

# セッション一覧を確認
bunsui session list
```

## 5. 診断

問題が発生した場合：

```bash
# 診断を実行
bunsui doctor

# AWS接続をチェック
bunsui doctor --check-aws
```

## 次のステップ

1. `TUTORIAL.md` を読んで、より詳細な使い方を学ぶ
2. 実際のAWSリソースと統合する
3. TUIモードを試す: `bunsui tui`
4. インタラクティブモードを試す: `bunsui interactive`

## 注意事項

- このツールは現在開発中のため、一部の機能は実装されていない可能性があります
- 実際のAWSリソースを使用する場合は、適切な認証情報とIAMロールが必要です
- サンプルファイルのAWSリソース（Lambda関数、S3バケットなど）は架空のものです 