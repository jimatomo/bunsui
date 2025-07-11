# Bunsui チュートリアル

このディレクトリには、Bunsuiの基本的な使い方を学ぶためのチュートリアルファイルが含まれています。

## ファイル一覧

### ドキュメント
- `QUICK_START.md` - 5分で始めるクイックスタートガイド
- `TUTORIAL.md` - 詳細なチュートリアル（全機能の説明）

### サンプルファイル
- `sample_pipeline.yaml` - ETLパイプラインの定義例（複雑な例）
- `simple_pipeline.yaml` - シンプルなパイプラインの定義例（初心者向け）

## 使い方

### 1. 初めての方

まず `QUICK_START.md` を読んで、基本的なコマンドを試してください：

```bash
# クイックスタートガイドを表示
cat QUICK_START.md

# 最初のコマンドを実行
bunsui version
```

### 2. 詳しく学びたい方

`TUTORIAL.md` には、すべての主要機能の説明が含まれています：

```bash
# チュートリアルを表示
cat TUTORIAL.md
```

### 3. 実際に試す

サンプルファイルを使って、実際のパイプラインを作成してみましょう：

```bash
# シンプルなパイプラインから始める
bunsui pipeline create -f simple_pipeline.yaml --dry-run

# より複雑なパイプラインに挑戦
bunsui pipeline create -f sample_pipeline.yaml --dry-run
```

## 主な学習ポイント

1. **基本コマンド**: version, help, doctor
2. **パイプライン管理**: create, list, show, update, delete
3. **セッション管理**: start, list, stop
4. **ログ確認**: show, フィルタリング
5. **設定管理**: init, get, set
6. **インタラクティブモード**: 対話的な操作

## 注意事項

- このチュートリアルは開発環境での使用を想定しています
- 実際のAWSリソースは設定されていないため、一部のコマンドはエラーになる可能性があります
- 本番環境で使用する前に、適切なAWS認証情報とリソースの設定が必要です

## サポート

問題が発生した場合：

1. `bunsui doctor` で診断を実行
2. プロジェクトのGitHubイシューを確認
3. より詳細なドキュメントは `docs/` ディレクトリを参照

Happy pipelining with Bunsui! 🚀 