# CLI Reference

## 概要

Bunsui CLIは、パイプラインの管理、セッションの制御、ログの表示、設定の管理を行うためのコマンドラインインターフェースです。

## コマンド一覧

### パイプライン管理

#### `bunsui pipeline create`

新しいパイプラインを作成します。

```bash
bunsui pipeline create --file pipeline.yaml
```

**オプション:**
- `--file, -f`: パイプライン定義ファイルのパス（必須）

#### `bunsui pipeline list`

パイプライン一覧を表示します。

```bash
bunsui pipeline list --format table
```

**オプション:**
- `--format`: 出力形式（table, json, yaml）

#### `bunsui pipeline update`

既存のパイプラインを更新します。

```bash
bunsui pipeline update --name "pipeline-name" --file pipeline.yaml
```

#### `bunsui pipeline delete`

パイプラインを削除します。

```bash
bunsui pipeline delete --name "pipeline-name"
```

### セッション管理

#### `bunsui session start`

パイプラインセッションを開始します。

```bash
bunsui session start --pipeline "pipeline-name" --parameters key=value
```

**オプション:**
- `--pipeline`: パイプライン名（必須）
- `--parameters`: パラメータ（key=value形式）

#### `bunsui session pause`

セッションを一時停止します。

```bash
bunsui session pause --session-id "session-id"
```

#### `bunsui session resume`

セッションを再開します。

```bash
bunsui session resume --session-id "session-id"
```

#### `bunsui session cancel`

セッションをキャンセルします。

```bash
bunsui session cancel --session-id "session-id"
```

#### `bunsui session status`

セッションのステータスを表示します。

```bash
bunsui session status --session-id "session-id"
```

### ログ管理

#### `bunsui logs tail`

ログをリアルタイムで表示します。

```bash
bunsui logs tail --session-id "session-id"
```

#### `bunsui logs filter`

ログをフィルタリングして表示します。

```bash
bunsui logs filter --session-id "session-id" --level INFO
```

**オプション:**
- `--level`: ログレベル（DEBUG, INFO, WARNING, ERROR）
- `--from`: 開始時刻
- `--to`: 終了時刻

#### `bunsui logs download`

ログをダウンロードします。

```bash
bunsui logs download --session-id "session-id" --output logs.json
```

### 設定管理

#### `bunsui config set`

設定値を設定します。

```bash
bunsui config set aws.region ap-northeast-1
bunsui config set aws.profile default
```

#### `bunsui config get`

設定値を取得します。

```bash
bunsui config get aws.region
```

#### `bunsui config list`

全設定を表示します。

```bash
bunsui config list
```

## インタラクティブモード

```bash
bunsui interactive
```

インタラクティブモードでは、対話的にコマンドを実行できます。

## グローバルオプション

- `--config`: 設定ファイルのパス
- `--verbose, -v`: 詳細出力
- `--quiet, -q`: 静寂モード
- `--help, -h`: ヘルプ表示 