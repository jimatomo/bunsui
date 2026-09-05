# bunsui

ローカル完結のデータ基盤。

**DuckDB** をウェアハウス、**dbt** を変換レイヤ、**SQLite** をコントロールプレーン（ジョブ / アセット状態）として使うローカルデータプラットフォームです。

## Architecture

```
┌──────────────────┐     HTTP      ┌──────────────────┐
│  React UI (web)  │◄─────────────►│  Hono API (web)  │
└──────────────────┘               └────────┬─────────┘
                                            │ read SQLite
                                            │ spawn CLI for Run
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
depends_on: []     # 他ジョブ名（`job run` がトポロジカル波で辿り、独立兄弟は並列）
config:
  command: build   # run / build / test など
  select: example
  # retries: 2              # dbt only: native `dbt retry` attempts after failure (default 0)
  # retry_delay_seconds: 2  # wait before each `dbt retry` (default 2; dbt only)
```

ファイルは単一ジョブ、`jobs:` リスト、またはジョブの YAML リストのいずれでも可。宣言から外したジョブは削除せず `enabled=0` にします。

`bunsui job run <name>` は yaml を sync したうえで **`depends_on` をトポロジカル波（wave）で辿り**、indegree 0 の兄弟は並列実行し、前提成功後に下流へ進みます（サイクル / 欠落は実行前にエラー。波内で失敗したら in-flight の兄弟は完了待ち、その後の波は開始しない）。`--no-deps` で従来どおり名前付きジョブだけを実行できます。**python sync** は同一プロセス内で完結します。**python async** は子プロセスで callable を実行し、親は **`job_runs.status` を SQLite でポーリング**して完了を検知します（チェイン中の上流 async も同様に待機）。**dbt** はプロジェクトの `dbt/` で CLI を sync サブプロセスとして実行し、stdout/stderr を `logs/` に保存して `logs` テーブルへ紐づけ、成功・失敗いずれでも `target/run_results.json` を `artifacts/` に保持して **`assets` / `asset_materializations` に upsert** します。CLI が非ゼロ終了した場合、`target/run_results.json` が残っていれば `config.retries`（追加の **`dbt retry`** 回数、デフォルト 0）と `config.retry_delay_seconds`（デフォルト 2）でネイティブ `dbt retry` を実行します（**同一 argv の再実行ではない**。**dbt のみ**。python には適用しません。1 本の `job_runs` 行で最終結果を記録）。`run_results.json` の保持は `ArtifactStore`（既定はローカル `artifacts/`）経由で、クラウドオブジェクトストレージへ差し替え可能な DI になっています。`--no-wait` で async の leaf を起動だけして戻ることもできます。サンプルは `example_dbt` → `example_python` の小さなチェインです（`example_python_async` は単独）。

```bash
uv run bunsui job run example_python --project ../my-project          # dbt → python
uv run bunsui job run example_python --no-deps --project ../my-project
uv run bunsui job run example_dbt --project ../my-project
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
# Jobs UI の Run ボタン → POST /api/jobs/:name/run（CLI と同じ depends_on チェイン）
bun test
```

単体起動:

```bash
bun run dev:api
bun run dev:ui
```

## Roadmap

**いま動くもの:** プロジェクト初期化（`bunsui init`）、`bunsui job sync`、`bunsui job run`（`depends_on` トポロジカル波 + 独立兄弟の並列 fan-out / `--no-deps`、python sync / async → `job_runs`、async は SQLite ポーリング、dbt sync → logs + `run_results.json` → assets、**dbt native `dbt retry` + `ArtifactStore`**）、SQLite スキーマ、Hono API（読み取り + Jobs の **Run**）、React UI（Jobs の最終ラン表示 / Run ボタン / Assets / Logs）、テストと CI。

**これから実装するもの:**

- stdout の増分 / ストリーミングパース（ログ UI 向け）
- スケジューリング / cron
- CSV/Parquet の DuckDB ロード
- 本番スケジューリング
- UI でのリトライ設定・python リトライ
- S3/GCS などクラウド向け `ArtifactStore` 実装

## License

MIT — see [LICENSE](LICENSE).
