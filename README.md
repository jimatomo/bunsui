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
    warehouse.duckdb       # DuckDB ウェアハウス
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
  command: build   # run / build / test など
  select: example
```

ファイルは単一ジョブ、`jobs:` リスト、またはジョブの YAML リストのいずれでも可。宣言から外したジョブは削除せず `enabled=0` にします。

`bunsui job run <name>` は yaml を sync したうえで **python** または **dbt** ジョブを実行し、`job_runs` に running → succeeded / failed を書き込みます（`depends_on` は辿りません）。**python sync** は同一プロセス内で完結します。**python async** は子プロセスで callable を実行し、親は **`job_runs.status` を SQLite でポーリング**して完了を検知します。**dbt** はプロジェクトの `dbt/` で CLI を sync サブプロセスとして実行し、stdout/stderr を `logs/` に保存して `logs` テーブルへ紐づけ、成功・失敗いずれでも `target/run_results.json` を `artifacts/` に保持して **`assets` / `asset_materializations` に upsert** します。`--no-wait` で async python を起動だけして戻ることもできます。サンプルの `example_dbt`（`build` + `not_null` テスト）/ `example_python` / `example_python_async` がそのまま動きます。

```bash
uv run bunsui job run example_dbt --project ../my-project
uv run bunsui job run example_python --project ../my-project
uv run bunsui job run example_python_async --project ../my-project
```

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
uv run bunsui job run example_dbt --project ../my-project
uv run bunsui job run example_python --project ../my-project
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

**いま動くもの:** プロジェクト初期化（`bunsui init`）、`bunsui job sync`、`bunsui job run`（python sync / async → `job_runs`、async は SQLite ポーリング、dbt sync → logs + `run_results.json` → assets）、SQLite スキーマ、Hono 読み取り API、React UI（Jobs の最終ラン表示 / Assets / Logs）、テストと CI。

**これから実装するもの:**

- dbt リトライ・stdout の増分パース
- 依存チェイン（`depends_on` の実行）
- CSV/Parquet の DuckDB ロード
- 本番スケジューリング

## License

MIT — see [LICENSE](LICENSE).
