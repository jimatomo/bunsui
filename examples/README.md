# Sample bunsui project

`uv run bunsui init` で生成したレイアウト例。API のローカル動作確認に使えます。

```bash
cd engine
uv run bunsui job sync --project ../examples/sample-project
uv run bunsui job run example_python --project ../examples/sample-project

export BUNSUI_PROJECT="$(pwd)/../examples/sample-project"
cd ../web && bun run dev:api
curl -s localhost:8787/api/jobs
```
