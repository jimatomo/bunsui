# bunsui web

Bun workspace for the bunsui HTTP API (Hono) and React UI.

```bash
cd web
bun install
bun run dev          # API :8787 + UI :5173
bun test             # API health/status tests
```

Point the API at a project SQLite DB:

```bash
export BUNSUI_PROJECT=/path/to/project   # reads .bunsui/control.sqlite
# or
export BUNSUI_SQLITE=/path/to/.bunsui/control.sqlite
bun run dev:api
```
