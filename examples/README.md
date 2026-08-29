# Sample bunsui project

`uv run bunsui init` で生成したレイアウト例。API のローカル動作確認に使えます。

```bash
export BUNSUI_PROJECT="$(pwd)/examples/sample-project"
cd web && bun run dev:api
curl -s localhost:8787/api/status
```
