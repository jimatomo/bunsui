# bunsui

ローカル完結のデータ基盤。

**DuckDB** をウェアハウス、**dbt** を変換レイヤ、**SQLite** をコントロールプレーン（ジョブ / アセット状態）として使うローカルデータプラットフォームです。

## Architecture

```
┌──────────────────┐     HTTP      ┌──────────────────┐
│  React UI (web)  │◄─────────────►│  Hono API (web)  │
└──────────────────┘               └────────┬─────────┘
                                            │ read
                                            ▼
                                   ┌──────────────────┐
                                   │ SQLite control   │
                                   │ jobs / assets /  │
                                   │ runs / logs …    │
                                   └────────▲─────────┘
                                            │ write
┌──────────────────┐                        │
│  Python engine   │────────────────────────┘
│  (uv / 3.14+)    │──── DuckDB warehouse
│                  │──── dbt project dir
└──────────────────┘
```

### Product rules

- **Job** = 実行単位（dbt コマンドまたは任意の Python）。順序付き依存を持てる。チェインは sync / async。async 完了は **SQLite のステータス書き込みをポーリング**して検知する。
- **Asset** = Dagster 風の状態単位（SQLite）。dbt アセットは `run_results.json` の全ノードから作る。モデルに紐づくテストは親モデルの子（`parent_asset_id`）。テスト失敗は親モデルアセットのエラーとして扱う。
- dbt 取り込みの正は **`run_results.json`**。一定期間保持し、stdout ログもランに紐づけて UI 向けに保存する。stdout の増分 SQLite パースは任意の拡張として検討する。

## Layout

```
engine/                 # Python package (uv, requires-python >=3.14)
web/                    # bun workspace: apps/api (Hono) + apps/ui (React)
examples/sample-project # bunsui init で作ったサンプル
```

### bunsui プロジェクトの置き場

```
my-project/
  bunsui.yaml              # プロジェクト設定（小さな案件は inline jobs: も可）
  jobs/                    # ジョブ宣言（*.yaml / *.yml）
  .bunsui/
    control.sqlite         # コントロールプレーン
    warehouse.duckdb       # DuckDB ウェアハウス（ロード/クエリは未実装）
  dbt/                     # dbt プロジェクト
  artifacts/               # run_results.json など保持
  logs/                    # ランごとの stdout など
```

### Jobs

ジョブは **`jobs/*.yaml`** に分割して置くのが基本です（`bunsui init` もこの形）。小さな案件向けに `bunsui.yaml` の inline `jobs:` も使えます。どちらも `bunsui job sync` で SQLite の `jobs` テーブルへ反映します（実行はしません）。

```yaml
# jobs/example_dbt.yaml — 1 ファイル = 1 ジョブ（推奨）
name: example_dbt
type: dbt          # dbt | python
execution_mode: sync  # sync | async
depends_on: []     # 他ジョブ名（DAG 実行は未実装・JSON として保存のみ）
config:
  command: run
  select: example
```

ファイルは単一ジョブ、`jobs:` リスト、またはジョブの YAML リストのいずれでも可。宣言から外したジョブは削除せず `enabled=0` にします。

## Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/)（Python **3.14** を自動取得）
- [bun](https://bun.sh/) 1.x

システムに 3.14 が無くても、`uv` が 3.14 をダウンロードします。`requires-python` は `>=3.14` です。

### Engine

```bash
cd engine
uv sync
uv run bunsui init ../my-project --name my-project
uv run bunsui job sync --project ../my-project
uv run bunsui schema --project ../my-project
uv run pytest
```

### Web

```bash
cd web
bun install

# サンプル（または自分で init した）プロジェクトの SQLite を読む
export BUNSUI_PROJECT="$(pwd)/../examples/sample-project"
bun run dev
# API http://localhost:8787  /  UI http://localhost:5173
bun test
```

単体起動:

```bash
bun run dev:api
bun run dev:ui
```

## Roadmap

**いま動くもの:** プロジェクト初期化（`bunsui init`）、`bunsui job sync`（yaml → SQLite）、SQLite スキーマ、Hono 読み取り API、React UI（Jobs / Assets / Logs）、テストと CI。

**これから実装するもの:**

- Python ジョブの実行（callable）
- dbt CLI 実行・リトライ・`run_results.json` 取り込み・stdout の増分パース
- ジョブランナー（sync/async、依存チェイン、ポーリングループ）
- CSV/Parquet の DuckDB ロード
- 本番スケジューリング

## License

MIT — see [LICENSE](LICENSE).
